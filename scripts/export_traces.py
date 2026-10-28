"""Exporta las conversaciones guardadas, con su traza, a un informe Markdown compacto.

Sirve para revisar los guiones y calibrar (p. ej., la indagación de la HU-11) sin copiar y
pegar desde la auditoría web: un solo archivo trae, por hilo, el resumen, los mensajes y,
en cada respuesta, el alcance, la búsqueda, la evidencia, el respaldo, los recordatorios, las
alertas y la decisión de la regla de indagación.

Uso (en el PC de pruebas):
    python scripts/export_traces.py --since "2026-10-27 18:00" > trazas.md
    python scripts/export_traces.py --last 5
    python scripts/export_traces.py --thread 65c3d012

`--since` usa la hora local del equipo. La base se abre en solo lectura (por defecto
`DATABASE_PATH` o `data/cardio_materno.db`). Los mensajes fuera de alcance no se guardan, así
que no aparecen. No exporta datos personales: los usuarios solo existen como hash.
"""

import argparse
import os
import sqlite3
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (  # noqa: E402
    alert_from_row,
    message_from_row,
)
from cardio_materno.domain.conversation import ChatMessage, Role  # noqa: E402
from cardio_materno.domain.trace import (  # noqa: E402
    GroundingCheck,
    InquiryTrace,
    ReplyTrace,
)

DEFAULT_DATABASE = "data/cardio_materno.db"
DATABASE_VARIABLE = "DATABASE_PATH"
DEFAULT_LAST = 5
TIME_FORMAT = "%Y-%m-%d %H:%M"
SHORT_ID = 8
THREADS_QUERY = """
    SELECT t.id, t.domain, t.summary, t.status, t.created_at, t.updated_at,
        (SELECT ci.channel FROM channel_identities ci WHERE ci.user_id = t.user_id LIMIT 1)
        AS channel
    FROM threads t ORDER BY t.created_at
"""
MESSAGES_QUERY = """
    SELECT m.thread_id, m.role, m.content, m.created_at, m.trace_json
    FROM messages m WHERE m.thread_id = ? ORDER BY m.seq
"""
ALERTS_QUERY = """
    SELECT a.thread_id, a.rule_ids_json, a.severity, a.origin, a.created_at
    FROM alerts a WHERE a.thread_id = ? ORDER BY a.seq
"""
ROLE_LABELS = {Role.USER: "👤 Persona", Role.ASSISTANT: "🤖 Asistente"}
PROGRESS_TEXT = {True: "sí", False: "no", None: "—"}
NO_CHANNEL = "sin canal"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Lee las opciones de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Exporta conversaciones con su traza.")
    parser.add_argument("--db", type=Path, default=None, help="Archivo SQLite de la base")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--since", help='Hilos creados desde esta hora local ("AAAA-MM-DD HH:MM")')
    choice.add_argument("--last", type=int, help="Últimos N hilos (por defecto 5)")
    choice.add_argument("--thread", help="Un hilo por el inicio de su identificador")
    return parser.parse_args(argv)


def database_path(option: Path | None) -> Path:
    """Ruta de la base: la opción, `DATABASE_PATH` o la ruta por defecto del proyecto."""
    path = option or Path(os.environ.get(DATABASE_VARIABLE) or DEFAULT_DATABASE)
    return path if path.is_absolute() else PROJECT_ROOT / path


def connect_read_only(path: Path) -> sqlite3.Connection:
    """Abre la base en solo lectura (no aplica migraciones ni bloquea la escritura).

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not path.exists():
        raise FileNotFoundError(f"No existe la base {path}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def select_threads(rows: list[sqlite3.Row], args: argparse.Namespace) -> list[sqlite3.Row]:
    """Filtra los hilos según `--thread`, `--since` o `--last` (en orden de creación)."""
    if args.thread:
        return [row for row in rows if row["id"].startswith(args.thread)]
    if args.since:
        since = datetime.strptime(args.since, TIME_FORMAT).astimezone()
        return [row for row in rows if datetime.fromisoformat(row["created_at"]) >= since]
    return rows[-(args.last or DEFAULT_LAST) :]


def local_time(value: datetime | str | None) -> str:
    """Fecha y hora local corta ("—" si no hay)."""
    if value is None:
        return "—"
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    return moment.astimezone().strftime(TIME_FORMAT)


def render_thread(connection: sqlite3.Connection, row: sqlite3.Row) -> list[str]:
    """Bloque de un hilo: cabecera, alertas y mensajes."""
    channel = row["channel"] or NO_CHANNEL
    lines = [
        f"## Hilo {row['id'][:SHORT_ID]} · {channel} · {row['domain']} · {row['status']}",
        f"Creado {local_time(row['created_at'])} · resumen: {row['summary']}",
    ]
    alerts = [alert_from_row(a) for a in connection.execute(ALERTS_QUERY, (row["id"],))]
    lines.extend(
        f"- 🚨 Alerta {', '.join(a.rule_ids)} · {a.severity} · {a.origin}"
        f" · {local_time(a.created_at)}"
        for a in alerts
    )
    for message_row in connection.execute(MESSAGES_QUERY, (row["id"],)):
        lines.extend(render_message(message_from_row(message_row)))
    return lines


def render_message(message: ChatMessage) -> list[str]:
    """Texto del mensaje y, en las respuestas, su traza."""
    label = ROLE_LABELS.get(message.role, str(message.role))
    lines = ["", f"**{label}** ({local_time(message.created_at)}): {message.content}"]
    if message.trace is not None:
        lines.extend(f"  - {line}" for line in trace_lines(message.trace))
    return lines


def trace_lines(trace: ReplyTrace) -> list[str]:
    """Datos de la traza que importan para revisar un turno."""
    lines = [
        f"alcance: {trace.scope or '—'} ({trace.scope_reason or 'sin motivo'})"
        f" · sobre salud: {'sí' if trace.about_health else 'no'}",
        f"síntomas: {'; '.join(trace.reported_symptoms) or 'ninguno'}"
        f" · signos: {', '.join(trace.reported_signs) or 'ninguno'}",
    ]
    if trace.reminded_rules:
        lines.append(f"recordatorio de: {', '.join(trace.reminded_rules)}")
    if trace.retrieval_status is not None:
        lines.extend(search_lines(trace))
    if trace.grounding is not None:
        lines.append(grounding_line(trace.grounding))
    if trace.inquiry is not None:
        lines.append(inquiry_line(trace.inquiry))
    return lines


def search_lines(trace: ReplyTrace) -> list[str]:
    """Consulta, estado de la búsqueda, evidencia con puntajes y citas."""
    widened = " · ampliada a los dos dominios" if trace.domain_fallback else ""
    best = f"{trace.best_score:.2f}" if trace.best_score is not None else "—"
    evidence = " | ".join(f"{e.label} {e.score:.2f} {e.category}" for e in trace.evidence)
    return [
        f"búsqueda: «{trace.search_query}»{widened} · {trace.retrieval_status} (mejor {best})",
        f"evidencia: {evidence or 'ninguna'}"
        f" · citas: {', '.join(trace.cited_evidence) or 'ninguna'}",
    ]


def grounding_line(check: GroundingCheck) -> str:
    """Frases respaldadas, uso del literal y frases descartadas."""
    line = f"respaldo: {check.supported}/{check.total} frases"
    if check.literal:
        line += f" · literal ({check.literal_shown}/{check.literal_total} frases del registro)"
    if check.dropped:
        line += " · descartadas: " + " / ".join(check.dropped)
    return line


def inquiry_line(inquiry: InquiryTrace) -> str:
    """Decisión de la regla de indagación (HU-11) y sus señales."""
    applied = "aplicada" if inquiry.applied else "observada"
    guidance = " · pide orientación" if inquiry.wants_guidance else ""
    return (
        f"indagación {applied}: {inquiry.mode} · turno {inquiry.turn} · s1 {inquiry.best_score:.2f}"
        f" · margen {inquiry.margin:.2f} · coincidencia {inquiry.agreement}"
        f" ({inquiry.top_category or '—'}) · avance {PROGRESS_TEXT[inquiry.progress]}"
        f" · sin avance {inquiry.stalled}{guidance}"
    )


def export(connection: sqlite3.Connection, args: argparse.Namespace) -> str:
    """Informe Markdown de los hilos seleccionados."""
    threads = select_threads(connection.execute(THREADS_QUERY).fetchall(), args)
    lines = [f"# Trazas exportadas ({len(threads)} hilos)"]
    for row in threads:
        lines.extend(["", *render_thread(connection, row)])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str]) -> int:
    """Imprime el informe; devuelve 1 si la base no existe."""
    args = parse_args(argv)
    try:
        connection = connect_read_only(database_path(args.db))
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        report = export(connection, args)
    finally:
        connection.close()
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
