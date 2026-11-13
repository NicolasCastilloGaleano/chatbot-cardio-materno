"""Exporta la hoja de la base de conocimiento (dos CSV) a `knowledge/kb/entries.jsonl`.

Uso:
    python scripts/export_sheet_kb.py <cardiovascular.csv> <materno_infantil.csv> [salida.jsonl]

Cada CSV es una pestaña de la hoja de Google descargada con *Archivo → Descargar → Valores
separados por comas*, con las columnas Categoría, Enfoque, Preguntas y Respuestas. El `id` se
calcula igual que en `kb_sync` (SHA-256 de dominio + categoría + pregunta + respuesta), así que
los registros que no cambian conservan su id. Solo usa la librería estándar.
"""

import csv
import hashlib
import json
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path

CARDIO_ARG = 1
MATERNAL_ARG = 2
OUTPUT_ARG = 3
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "knowledge" / "kb" / "entries.jsonl"
DOMAIN_BY_ARG = {CARDIO_ARG: "cardiovascular", MATERNAL_ARG: "materno_infantil"}
ID_SEPARATOR = "\x1f"
COLUMN_MAP = {
    "categoria": "category",
    "enfoque": "focus",
    "preguntas": "question",
    "pregunta": "question",
    "respuestas": "answer",
    "respuesta": "answer",
}
REQUIRED_COLUMNS = {"category", "question", "answer"}
SORT_FIELDS = ("domain", "category", "focus", "question")


class SheetFormatError(ValueError):
    """La pestaña exportada no tiene las columnas esperadas."""


def clean(value: str) -> str:
    """Normaliza los espacios, como `kb_sync`, para que no cambien el id."""
    return " ".join(value.split())


def normalize_header(value: str) -> str:
    """Pasa una cabecera a minúsculas y sin tildes (`Categoría` → `categoria`)."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower()


def compute_id(domain: str, category: str, question: str, answer: str) -> str:
    """Calcula el id del registro con la misma fórmula de `kb_sync`."""
    parts = [domain, category.casefold(), question.casefold(), answer.casefold()]
    return hashlib.sha256(ID_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def column_index(header: list[str]) -> dict[str, int]:
    """Ubica cada campo en la cabecera.

    Raises:
        SheetFormatError: Si falta una columna obligatoria.
    """
    index: dict[str, int] = {}
    for position, name in enumerate(header):
        field = COLUMN_MAP.get(normalize_header(name))
        if field and field not in index:
            index[field] = position
    missing = REQUIRED_COLUMNS - index.keys()
    if missing:
        raise SheetFormatError(f"Faltan columnas en la hoja: {sorted(missing)}. Cabecera: {header}")
    return index


def to_entries(domain: str, rows: list[list[str]]) -> list[dict[str, str]]:
    """Convierte las filas de una pestaña (con cabecera) en registros sin vacíos ni duplicados."""
    if not rows:
        return []
    index = column_index(rows[0])
    entries: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        values = {field: clean(row[i]) if i < len(row) else "" for field, i in index.items()}
        if not values["question"] or not values["answer"]:
            continue
        entry_id = compute_id(domain, values["category"], values["question"], values["answer"])
        entries.setdefault(entry_id, make_entry(entry_id, domain, values))
    return list(entries.values())


def make_entry(entry_id: str, domain: str, values: dict[str, str]) -> dict[str, str]:
    """Arma un registro en el formato de `entries.jsonl`."""
    return {
        "id": entry_id,
        "domain": domain,
        "category": values["category"],
        "focus": values.get("focus", ""),
        "question": values["question"],
        "answer": values["answer"],
    }


def read_csv(path: Path) -> list[list[str]]:
    """Lee un CSV en UTF-8 (con o sin BOM)."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def write_jsonl(entries: Iterable[dict[str, str]], output: Path) -> int:
    """Escribe los registros ordenados como la exportación anterior y devuelve cuántos son."""
    ordered = sorted(entries, key=lambda entry: tuple(entry[f] for f in SORT_FIELDS))
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(entry, ensure_ascii=False) for entry in ordered]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return len(ordered)


def main(argv: list[str]) -> int:
    """Punto de entrada del script."""
    if len(argv) <= MATERNAL_ARG:
        print(__doc__)
        return 1
    output = Path(argv[OUTPUT_ARG]) if len(argv) > OUTPUT_ARG else DEFAULT_OUTPUT
    entries = [
        entry
        for arg, domain in DOMAIN_BY_ARG.items()
        for entry in to_entries(domain, read_csv(Path(argv[arg])))
    ]
    print(f"{write_jsonl(entries, output)} registros exportados a {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
