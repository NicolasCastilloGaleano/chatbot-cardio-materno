"""Informe agregado de acceso a la atención en CSV (HU-18, ADR 0023).

Uso:
    python scripts/export_care_access.py [--db data/cardio_materno.db] [--since AAAA-MM]
                                         [--until AAAA-MM] > acceso.csv

Abre la base en solo lectura. Solo cuenta personas que hoy tienen aceptada la autorización
para informes (`users.research_consent`) y no han rechazado el consentimiento, y solo meses
cerrados. El mes es el de cada mensaje, así que un mes cerrado no recibe datos nuevos.
Los controles de publicación están en `application/care_access_report.py`.

Límite conocido: si alguien retira su autorización, deja de contar también en los meses ya
cerrados. Dos exportaciones del mismo mes hechas antes y después del retiro pueden diferir
y esa diferencia describe a quien se retiró. Por eso cada mes cerrado se debe **publicar
una sola vez**; volver a publicarlo es una decisión del responsable de protección de datos.

No es una estimación de Caldas: describe a quienes usaron el asistente y lo autorizaron.
"""

import argparse
import csv
import io
import json
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)]

from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (  # noqa: E402
    CareAccessCatalogError,
    load_care_access_catalog,
)
from cardio_materno.adapters.outbound.persistence.trace_codec import trace_from_dict  # noqa: E402
from cardio_materno.application.care_access_report import (  # noqa: E402
    CAVEAT,
    Observation,
    ReportPolicy,
    build_report,
)
from cardio_materno.domain.user import ConsentStatus  # noqa: E402
from scripts.export_traces import connect_read_only, database_path  # noqa: E402

REQUIRED_SCHEMA = 3
PERIOD_CHARS = 7
DEFAULT_CATALOG = PROJECT_ROOT / "knowledge" / "care_access.json"
# Trazas con datos de acceso de quienes autorizaron el informe, por mes (cerrado) del mensaje.
AUTHORIZED_TRACES = """
    SELECT t.user_id, substr(COALESCE(m.created_at, t.created_at), 1, 7) AS period,
           m.trace_json
    FROM messages m JOIN threads t ON t.id = m.thread_id JOIN users u ON u.id = t.user_id
    WHERE u.research_consent = ? AND u.consent_status != ? AND m.trace_json IS NOT NULL
      AND substr(COALESCE(m.created_at, t.created_at), 1, 7) < ?
      AND substr(COALESCE(m.created_at, t.created_at), 1, 7) >= ?
    ORDER BY m.seq
"""
HEADER = ("periodo", "grupo", "indicador", "personas")
EARLIEST_PERIOD = "0000-00"
OLD_SCHEMA_TEXT = (
    "La base tiene el esquema {version}; se necesita el {required}. "
    "Abre el asistente una vez para que se migre."
)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Lee las opciones de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Informe agregado de acceso a la atención.")
    parser.add_argument("--db", type=Path, default=None, help="Archivo SQLite de la base")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="care_access.json")
    parser.add_argument("--since", default=EARLIEST_PERIOD, help="Desde este mes (AAAA-MM)")
    parser.add_argument("--until", default=None, help="Hasta antes de este mes (AAAA-MM)")
    return parser.parse_args(argv)


def closed_until(requested: str | None, now: datetime) -> str:
    """Primer mes que NO se exporta: nunca posterior al mes en curso."""
    current = now.astimezone(UTC).strftime("%Y-%m")
    return min(requested, current) if requested else current


def collect(connection: sqlite3.Connection, since: str, until: str) -> list[Observation]:
    """Datos de acceso por persona y mes, solo de quienes autorizaron el informe."""
    accepted, refused = str(ConsentStatus.ACCEPTED), str(ConsentStatus.REJECTED)
    observations: list[Observation] = []
    for row in connection.execute(AUTHORIZED_TRACES, (accepted, refused, until, since)):
        access = trace_from_dict(json.loads(row["trace_json"])).care_access
        if access is not None and access.facts:
            observations.append(Observation(row["user_id"], row["period"], access.facts))
    return observations


def schema_version(connection: sqlite3.Connection) -> int:
    """Versión del esquema de la base (`PRAGMA user_version`)."""
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def export(connection: sqlite3.Connection, args: argparse.Namespace, now: datetime) -> list[str]:
    """Líneas del CSV, con la advertencia de alcance como comentario inicial."""
    catalog = load_care_access_catalog(args.catalog)
    observations = collect(connection, args.since, closed_until(args.until, now))
    rows = build_report(observations, catalog, ReportPolicy())
    lines = [f"# {CAVEAT}"]
    lines.append(",".join(HEADER))
    lines.extend(_csv_line(r.period, r.group, r.indicator, r.published) for r in rows)
    return lines


def _csv_line(*cells: str) -> str:
    """Una línea CSV con las comillas necesarias."""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow(cells)
    return buffer.getvalue()


def main(argv: Sequence[str]) -> int:
    """Imprime el CSV; devuelve 1 si falta la base, el catálogo o el esquema 3."""
    args = parse_args(argv)
    try:
        connection = connect_read_only(database_path(args.db))
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        version = schema_version(connection)
        if version < REQUIRED_SCHEMA:
            message = OLD_SCHEMA_TEXT.format(version=version, required=REQUIRED_SCHEMA)
            print(message, file=sys.stderr)
            return 1
        print("\n".join(export(connection, args, datetime.now(UTC))))
    except CareAccessCatalogError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
