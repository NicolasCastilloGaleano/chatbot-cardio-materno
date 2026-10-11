"""Exporta la base de conocimiento del piloto anterior a `knowledge/kb/entries.jsonl`.

Uso (una sola vez; solo lee la base del piloto):
    python scripts/export_pilot_kb.py <ruta a knowledge_base.db> [salida.jsonl]

La base del piloto (`kb_sync`) guarda una fila por versión editada de cada registro; aquí se
conserva solo la más reciente por (dominio, categoría, pregunta), igual que hacía su buscador.
Solo usa la librería estándar.
"""

import json
import sqlite3
import sys
from pathlib import Path

SOURCE_ARG = 1
OUTPUT_ARG = 2
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "knowledge" / "kb" / "entries.jsonl"
QUERY = """
    SELECT id_local, dominio, categoria, enfoque, pregunta, respuesta, fecha_sincronizacion
    FROM knowledge_entries
    ORDER BY dominio, categoria, enfoque, pregunta
"""


def read_rows(db_path: Path) -> list[sqlite3.Row]:
    """Lee todas las filas de `knowledge_entries` en modo solo lectura."""
    connection = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(QUERY).fetchall()
    finally:
        connection.close()


def latest_versions(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Conserva la versión más reciente de cada (dominio, categoría, pregunta)."""
    latest: dict[tuple[str, str, str], sqlite3.Row] = {}
    for row in rows:
        key = (row["dominio"], row["categoria"].casefold(), row["pregunta"].casefold())
        current = latest.get(key)
        if current is None or row["fecha_sincronizacion"] > current["fecha_sincronizacion"]:
            latest[key] = row
    return list(latest.values())


def to_entry(row: sqlite3.Row) -> dict[str, str]:
    """Convierte una fila del piloto al formato de `entries.jsonl`."""
    return {
        "id": row["id_local"],
        "domain": row["dominio"],
        "category": row["categoria"],
        "focus": row["enfoque"],
        "question": row["pregunta"],
        "answer": row["respuesta"],
    }


def write_jsonl(entries: list[dict[str, str]], output: Path) -> None:
    """Escribe una entrada JSON por línea, en UTF-8 y orden estable."""
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    """Punto de entrada del script."""
    if len(argv) <= SOURCE_ARG:
        print(__doc__)
        return 1
    output = Path(argv[OUTPUT_ARG]) if len(argv) > OUTPUT_ARG else DEFAULT_OUTPUT
    entries = [to_entry(row) for row in latest_versions(read_rows(Path(argv[SOURCE_ARG])))]
    write_jsonl(entries, output)
    print(f"{len(entries)} registros exportados a {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
