"""Genera `knowledge/kb/provenance.json`: de dónde viene cada registro de la base.

Uso:
    python scripts/build_kb_provenance.py

El archivo acompaña a `entries.jsonl` sin modificarlo (cambiarlo obligaría a reconstruir el
índice). Para cada registro indica el lote en que entró a la base, el estado de revisión de
ese lote y, cuando existe, las fuentes del catálogo que citó su borrador. Se arma solo con
datos del repositorio:

- el lote, con la versión de `entries.jsonl` de los commits de `BATCH_COMMITS` (requiere git);
- las fuentes por registro, con la columna *Fuente* de `borradores-kb/ronda-2/*.csv`;
- el catálogo de fuentes, con la tabla de `docs/04-datos/fuentes-base-conocimiento.md`.

No decide nada clínico: el estado de revisión de cada lote es el que el equipo registró en
`knowledge/kb/README.md`. Solo usa la librería estándar.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_sheet_kb import clean, normalize_header, read_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = ROOT / "knowledge" / "kb" / "entries.jsonl"
OUTPUT = ROOT / "knowledge" / "kb" / "provenance.json"
SOURCES_DOC = ROOT / "docs" / "04-datos" / "fuentes-base-conocimiento.md"
DRAFTS = ROOT / "docs" / "04-datos" / "borradores-kb" / "ronda-2"
ENTRIES_GIT_PATH = "knowledge/kb/entries.jsonl"
VERIFIED_HEADING = "## Fuentes verificadas"
SOURCE_SEPARATOR = ";"
ORIGINAL, EXPANSION, ROUND_2 = "original", "ampliacion_b035", "ronda_2"
# Último commit en el que la base contenía solo los lotes anteriores a cada ampliación.
BATCH_COMMITS = {ORIGINAL: "333fdea", EXPANSION: "41cb8fd"}
# Estados tal como los registró el equipo en knowledge/kb/README.md. Ninguno es validación
# clínica: esa sigue pendiente para toda la base (B-019).
BATCHES = {
    ORIGINAL: {
        "label": "Base original (2026-10-10)",
        "review": "validada_para_prototipo",
        "review_label": "Aceptada para el prototipo por el líder del proyecto",
    },
    EXPANSION: {
        "label": "Ampliación B-035 (2026-11-10)",
        "review": "pendiente_de_validacion",
        "review_label": "Pendiente de validación del equipo",
    },
    ROUND_2: {
        "label": "Ronda 2 con fuentes (2026-11-12)",
        "review": "revisada_por_el_equipo",
        "review_label": "Revisada por el equipo; redactada a partir de fuentes citadas",
    },
}
ABOUT = (
    "Procedencia de los registros de entries.jsonl. Generado por "
    "scripts/build_kb_provenance.py: no editar a mano. Los registros que no aparecen en "
    "'entries' son del lote 'default_batch'. La validación clínica sigue pendiente para "
    "toda la base."
)

Json = dict[str, object]


def ids_at(commit: str) -> set[str]:
    """Identificadores de la base en un commit."""
    shown = subprocess.run(  # noqa: S603, S607 - git del propio repositorio, sin datos externos
        ["git", "show", f"{commit}:{ENTRIES_GIT_PATH}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    lines = shown.stdout.decode("utf-8").splitlines()
    return {json.loads(line)["id"] for line in lines if line.strip()}


def load_catalog(path: Path) -> dict[str, Json]:
    """Fuentes verificadas del catálogo: id → entidad, título, versión y URL."""
    table = path.read_text(encoding="utf-8").split(VERIFIED_HEADING, 1)[1].split("\n## ", 1)[0]
    catalog: dict[str, Json] = {}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0].startswith("`"):  # noqa: PLR2004
            continue
        catalog[cells[0].strip("`")] = {
            "entity": cells[1],
            "title": cells[2],
            "version": cells[3],
            "url": cells[4],
        }
    return catalog


def draft_sources(folder: Path) -> dict[tuple[str, str], list[str]]:
    """(pregunta, respuesta) de cada borrador → identificadores de sus fuentes."""
    sources: dict[tuple[str, str], list[str]] = {}
    for path in sorted(folder.glob("*.csv")):
        rows = read_csv(path)
        columns = {normalize_header(name): index for index, name in enumerate(rows[0])}
        for row in rows[1:]:
            key = (clean(row[columns["preguntas"]]), clean(row[columns["respuestas"]]))
            cited = row[columns["fuente"]].split(SOURCE_SEPARATOR)
            sources[key] = [source.strip() for source in cited if source.strip()]
    return sources


def batch_of(entry_id: str, snapshots: dict[str, set[str]]) -> str:
    """Lote en el que el registro entró a la base."""
    if entry_id in snapshots[ORIGINAL]:
        return ORIGINAL
    return EXPANSION if entry_id in snapshots[EXPANSION] else ROUND_2


def build(entries: list[Json], snapshots: dict[str, set[str]]) -> Json:
    """Arma el contenido de `provenance.json`."""
    drafts = draft_sources(DRAFTS)
    records: dict[str, Json] = {}
    for entry in entries:
        entry_id = str(entry["id"])
        batch = batch_of(entry_id, snapshots)
        cited = drafts.get((clean(str(entry["question"])), clean(str(entry["answer"]))), [])
        if batch != ORIGINAL or cited:
            records[entry_id] = {"batch": batch, "sources": cited}
    return {
        "_about": ABOUT,
        "default_batch": ORIGINAL,
        "batches": BATCHES,
        "sources": load_catalog(SOURCES_DOC),
        "entries": records,
    }


def main() -> int:
    """Punto de entrada del script."""
    lines = ENTRIES.read_text(encoding="utf-8").splitlines()
    entries: list[Json] = [json.loads(line) for line in lines if line.strip()]
    snapshots = {batch: ids_at(commit) for batch, commit in BATCH_COMMITS.items()}
    data = build(entries, snapshots)
    OUTPUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    records = data["entries"]
    assert isinstance(records, dict)
    with_sources = sum(1 for record in records.values() if record["sources"])
    print(f"{OUTPUT.name}: {len(entries)} registros, {with_sources} con fuente citada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
