"""Informe de vacíos de la base de conocimiento para el equipo clínico (HU-15, B-032).

Lista los turnos de salud en que la persona no recibió orientación (abstención o cierre de la
indagación), agrupados por categoría de la base, con la consulta de búsqueda, la mejor
similitud y los registros que el selector descartó. Sirve para decidir qué contenido agregar.

Uso (en el PC de pruebas):
    python scripts/report_gaps.py > vacios.md
    python scripts/report_gaps.py --since "2026-11-01 00:00" > vacios.md

`--since` usa la hora local del equipo y filtra por la hora de la respuesta. La base se abre
en solo lectura. No muestra el mensaje de la persona ni identificadores: solo la consulta que
reformuló el análisis. Aun así, revisa el informe antes de compartirlo fuera del equipo.
"""

import argparse
import sqlite3
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (  # noqa: E402
    message_from_row,
)
from cardio_materno.application.gaps import Gap, GapGroup, gap_of, group_gaps  # noqa: E402
from cardio_materno.domain.conversation import ChatMessage, Role  # noqa: E402
from scripts.export_traces import (  # noqa: E402
    MESSAGES_QUERY,
    THREADS_QUERY,
    TIME_FORMAT,
    connect_read_only,
    database_path,
)

SCORE_FORMAT = "{:.2f}"
PRIVACY_NOTE = (
    "Solo se muestran consultas reformuladas por el análisis: ni mensajes de las personas ni "
    "identificadores. Revisa el informe antes de compartirlo fuera del equipo."
)
EMPTY_TEXT = "No hay turnos sin orientación en el periodo."


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Lee las opciones de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Informe de vacíos de la base.")
    parser.add_argument("--db", type=Path, default=None, help="Archivo SQLite de la base")
    parser.add_argument("--since", help='Respuestas desde esta hora local ("AAAA-MM-DD HH:MM")')
    return parser.parse_args(argv)


def collect_gaps(connection: sqlite3.Connection, since: datetime | None) -> list[Gap]:
    """Vacíos de todas las respuestas del asistente desde `since` (todas si es None)."""
    gaps: list[Gap] = []
    for thread in connection.execute(THREADS_QUERY).fetchall():
        for row in connection.execute(MESSAGES_QUERY, (thread["id"],)).fetchall():
            message = message_from_row(row)
            gap = gap_of(message.content, message.trace) if in_period(message, since) else None
            if gap is not None:
                gaps.append(gap)
    return gaps


def in_period(message: ChatMessage, since: datetime | None) -> bool:
    """True si es una respuesta del asistente desde `since` (todas, si no se filtra)."""
    if message.role is not Role.ASSISTANT:
        return False
    if since is None:
        return True
    return message.created_at is not None and message.created_at >= since


def render(groups: Sequence[GapGroup], since: str | None) -> str:
    """Informe Markdown: resumen y una sección por categoría."""
    total = sum(len(group.gaps) for group in groups)
    period = f"desde {since}" if since else "todo el historial"
    lines = [
        "# Vacíos de la base de conocimiento",
        "",
        f"Periodo: {period} · Turnos sin orientación: {total} · Categorías: {len(groups)}",
        "",
        PRIVACY_NOTE,
        "",
    ]
    if not groups:
        lines.append(EMPTY_TEXT)
    for group in groups:
        lines += render_group(group)
    return "\n".join(lines) + "\n"


def render_group(group: GapGroup) -> list[str]:
    """Sección de una categoría: tabla de consultas y registros descartados."""
    best = SCORE_FORMAT.format(group.best_score)
    lines = [
        f"## {group.category} · {len(group.gaps)} turnos · mejor similitud {best}",
        "",
        "| Consulta de búsqueda | Veces | Motivo | Mejor similitud |",
        "|---|---|---|---|",
    ]
    counts = Counter((gap.query, gap.reason) for gap in group.gaps)
    for (query, reason), times in counts.most_common():
        score = max(g.best_score for g in group.gaps if (g.query, g.reason) == (query, reason))
        lines.append(f"| {query or '—'} | {times} | {reason} | {SCORE_FORMAT.format(score)} |")
    rejected = sorted({record for gap in group.gaps for record in gap.rejected})
    if rejected:
        lines += ["", "Registros que el selector descartó:", *(f"- {r}" for r in rejected)]
    return [*lines, ""]


def main(argv: Sequence[str]) -> int:
    """Imprime el informe; devuelve 1 si la base no existe."""
    args = parse_args(argv)
    since = datetime.strptime(args.since, TIME_FORMAT).astimezone() if args.since else None
    try:
        connection = connect_read_only(database_path(args.db))
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        groups = group_gaps(collect_gaps(connection, since))
    finally:
        connection.close()
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    sys.stdout.write(render(groups, args.since))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
