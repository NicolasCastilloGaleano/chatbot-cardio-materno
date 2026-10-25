"""Convierte la hoja maestra de la base v2 (`RAG_2.xlsx`) en los archivos que lee el asistente.

Uso:
    python scripts/convert_rag_xlsx.py <ruta a RAG_2.xlsx> [carpeta de salida]

Genera `entries.jsonl` (un registro por fila) y `cuadros.jsonl` (un cuadro por motivo) en la
carpeta de salida (por defecto `knowledge/kb/`, que **reemplaza la base actual**). Antes de
escribir valida la hoja completa: columnas, celdas obligatorias, enfoque, etapa y ruta
coherentes, 12 etapas por cuadro y datos del cuadro iguales en sus 12 filas. Si hay un error,
no escribe nada. Después hay que reconstruir el índice: python run_build_kb_index.py
Solo usa la biblioteca estándar (ADR 0017).
"""

import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from cardio_materno.adapters.outbound.rag.knowledge_files import (  # noqa: E402
    case_profile_to_dict,
    entry_to_dict,
    write_jsonl,
)
from cardio_materno.application.evidence import EvidencePolicy  # noqa: E402
from cardio_materno.domain.conversation import Domain  # noqa: E402
from cardio_materno.domain.knowledge import (  # noqa: E402
    CaseProfile,
    Focus,
    KnowledgeEntry,
    Route,
    Stage,
    missing_stages,
)
from scripts.xlsx_reader import Rows, XlsxError, read_sheets  # noqa: E402

SOURCE_ARG = 1
OUTPUT_ARG = 2
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "knowledge" / "kb"
ENTRIES_FILE = "entries.jsonl"
CASES_FILE = "cuadros.jsonl"
# Índice sugerido para probar la base v2 sin tocar el de la v1 (MIG-07).
TRIAL_INDEX_DIR = "data/kb_index_v2"
HEADER_ROW = 1  # Número de fila (como en Excel) de los encabezados.
LIST_SEPARATOR = "|"
ID_TEMPLATE = "{domain}:{motive}:{stage}"
# Las respuestas más largas se recortan al mostrarlas al agente (`item_max_chars`).
MAX_ANSWER_CHARS = EvidencePolicy().item_max_chars

SHEET_DOMAINS = {
    "CARDIOVASCULAR": Domain.CARDIOVASCULAR,
    "MATERNO-INFANTIL": Domain.MATERNAL_CHILD,
}


class Column(StrEnum):
    """Columnas de la hoja maestra (encabezados exactos)."""

    CATEGORY = "Categoría"
    FOCUS = "Enfoque"
    QUESTION = "Preguntas"
    ANSWER = "Respuestas"
    MOTIVE = "Motivo"
    STAGE = "Etapa"
    ROUTE = "Ruta"
    CLINICAL_READING = "Lectura clínica"
    DATA_TO_COLLECT = "Datos a extraer"
    ESCALATION_SIGNS = "Señales de escalamiento"
    BASE_ROUTE = "Ruta base del cuadro"
    SOURCE = "Fuente"
    VALIDATED_BY = "Validado por"
    VALIDATED_AT = "Fecha validación"


# Columnas que deben existir pero pueden estar vacías mientras no haya validación (B-019).
OPTIONAL_COLUMNS = frozenset({Column.SOURCE, Column.VALIDATED_BY, Column.VALIDATED_AT})


class ConversionError(ValueError):
    """La hoja no tiene la estructura esperada."""


@dataclass(frozen=True)
class SheetRow:
    """Fila de datos de una hoja, con su ubicación para los mensajes de error.

    Attributes:
        sheet: Nombre de la hoja.
        number: Número de fila, como lo muestra Excel.
        domain: Dominio de la hoja.
        cells: Texto de cada columna (sin espacios al inicio ni al final).
    """

    sheet: str
    number: int
    domain: Domain
    cells: dict[Column, str]

    @property
    def location(self) -> str:
        """Ubicación legible de la fila."""
        return f"{self.sheet}, fila {self.number}"


@dataclass
class Conversion:
    """Resultado de convertir la hoja: registros, cuadros, errores y advertencias."""

    entries: list[KnowledgeEntry] = field(default_factory=list)
    profiles: dict[str, CaseProfile] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# --- Lectura de las hojas ---------------------------------------------------------------------


def rows_of_book(sheets: dict[str, Rows]) -> list[SheetRow]:
    """Filas de datos de todas las hojas del libro.

    Raises:
        ConversionError: Si hay una hoja desconocida o le faltan columnas.
    """
    unknown = sorted(set(sheets) - set(SHEET_DOMAINS))
    if unknown:
        raise ConversionError(f"Hojas desconocidas: {unknown}. Se esperan {list(SHEET_DOMAINS)}")
    return [
        row
        for name, rows in sheets.items()
        for row in rows_of_sheet(name, rows, SHEET_DOMAINS[name])
    ]


def rows_of_sheet(name: str, rows: Rows, domain: Domain) -> list[SheetRow]:
    """Filas de datos de una hoja (sin la de encabezados ni las filas vacías).

    Raises:
        ConversionError: Si a la hoja le faltan columnas.
    """
    header = [cell.strip() for cell in rows[0]] if rows else []
    missing = [column.value for column in Column if column.value not in header]
    if missing:
        raise ConversionError(f"A la hoja {name} le faltan las columnas: {missing}")
    positions = {column: header.index(column.value) for column in Column}
    return [
        SheetRow(name, number, domain, cells_of(row, positions))
        for number, row in enumerate(rows[1:], start=HEADER_ROW + 1)
        if any(cell.strip() for cell in row)
    ]


def cells_of(row: list[str], positions: dict[Column, int]) -> dict[Column, str]:
    """Texto de cada columna de una fila (las celdas que faltan quedan vacías)."""
    return {
        column: row[index].strip() if index < len(row) else ""
        for column, index in positions.items()
    }


# --- Conversión y validación ------------------------------------------------------------------


def convert(rows: Sequence[SheetRow]) -> Conversion:
    """Convierte las filas en registros y cuadros, acumulando todos los errores.

    Args:
        rows: Filas de datos del libro.

    Returns:
        La conversión; si `errors` no está vacío, no se debe escribir nada.
    """
    result = Conversion()
    for row in rows:
        add_row(result, row)
    for motive, stages in missing_stages(result.entries).items():
        result.errors.append(f"Al cuadro '{motive}' le faltan etapas: {[str(s) for s in stages]}")
    result.warnings.extend(content_warnings(result.entries))
    return result


def add_row(result: Conversion, row: SheetRow) -> None:
    """Agrega el registro y el cuadro de una fila, o el error que impide hacerlo."""
    empty = [c.value for c in Column if c not in OPTIONAL_COLUMNS and not row.cells[c]]
    if empty:
        result.errors.append(f"{row.location}: celdas vacías en {empty}")
        return
    try:
        entry, profile = build_entry(row), build_profile(row)
    except ValueError as error:
        result.errors.append(f"{row.location}: {error}")
        return
    if any(existing.id == entry.id for existing in result.entries):
        result.errors.append(f"{row.location}: el cuadro ya tiene un registro de esa etapa")
        return
    result.entries.append(entry)
    add_profile(result, profile, row)


def add_profile(result: Conversion, profile: CaseProfile, row: SheetRow) -> None:
    """Registra el cuadro; sus datos deben ser iguales en todas sus filas."""
    known = result.profiles.setdefault(profile.motive, profile)
    if known != profile:
        result.errors.append(
            f"{row.location}: los datos del cuadro '{profile.motive}' (categoría, lectura "
            "clínica, datos a extraer, señales o ruta base) no coinciden con sus otras filas"
        )


def build_entry(row: SheetRow) -> KnowledgeEntry:
    """Registro de la base a partir de una fila.

    Raises:
        ValueError: Si el enfoque, la etapa o la ruta no son válidos o no son coherentes.
    """
    cells = row.cells
    stage = Stage(cells[Column.STAGE])
    motive = cells[Column.MOTIVE]
    return KnowledgeEntry(
        id=ID_TEMPLATE.format(domain=row.domain, motive=motive, stage=stage),
        domain=row.domain,
        category=cells[Column.CATEGORY],
        focus=Focus(cells[Column.FOCUS]),
        question=cells[Column.QUESTION],
        answer=cells[Column.ANSWER],
        motive=motive,
        stage=stage,
        route=Route(cells[Column.ROUTE]),
        source=cells[Column.SOURCE],
        validated_by=cells[Column.VALIDATED_BY],
        validated_at=cells[Column.VALIDATED_AT],
    )


def build_profile(row: SheetRow) -> CaseProfile:
    """Cuadro (datos comunes del motivo) a partir de una fila.

    Raises:
        ValueError: Si la ruta base no es válida.
    """
    cells = row.cells
    return CaseProfile(
        motive=cells[Column.MOTIVE],
        domain=row.domain,
        category=cells[Column.CATEGORY],
        clinical_reading=cells[Column.CLINICAL_READING],
        data_to_collect=split_list(cells[Column.DATA_TO_COLLECT]),
        escalation_signs=split_list(cells[Column.ESCALATION_SIGNS]),
        base_route=Route(cells[Column.BASE_ROUTE]),
    )


def split_list(text: str) -> tuple[str, ...]:
    """Elementos de una celda separada por "|" (sin vacíos)."""
    return tuple(item.strip() for item in text.split(LIST_SEPARATOR) if item.strip())


def content_warnings(entries: Sequence[KnowledgeEntry]) -> list[str]:
    """Advertencias que no impiden convertir: respuestas largas y registros sin validar."""
    warnings = [
        f"{e.id}: la respuesta tiene {len(e.answer)} caracteres; el agente solo ve "
        f"{MAX_ANSWER_CHARS}"
        for e in entries
        if len(e.answer) > MAX_ANSWER_CHARS
    ]
    unvalidated = sum(1 for e in entries if not (e.source and e.validated_by and e.validated_at))
    if unvalidated:
        warnings.append(
            f"{unvalidated} de {len(entries)} registros no tienen Fuente, Validado por y Fecha "
            "validación (B-019): la base no se puede usar con personas reales sin validarla"
        )
    return warnings


# --- Informe y escritura ----------------------------------------------------------------------


def report_lines(result: Conversion) -> list[str]:
    """Resumen de la conversión para la consola."""
    lines = [f"Registros: {len(result.entries)} · cuadros: {len(result.profiles)}"]
    lines += [f"  {name}: {count}" for name, count in counts(result.entries).items()]
    lines += [f"ADVERTENCIA: {warning}" for warning in result.warnings]
    lines += [f"ERROR: {error}" for error in result.errors]
    return lines


def counts(entries: Sequence[KnowledgeEntry]) -> dict[str, int]:
    """Cantidad de registros por dominio, enfoque y etapa."""
    tally = Counter(f"dominio {e.domain}" for e in entries)
    tally.update(f"enfoque {e.focus}" for e in entries)
    tally.update(f"etapa {e.stage}" for e in entries)
    return dict(sorted(tally.items()))


def write_outputs(result: Conversion, output_dir: Path) -> None:
    """Escribe `entries.jsonl` y `cuadros.jsonl` en la carpeta de salida."""
    write_jsonl((entry_to_dict(entry) for entry in result.entries), output_dir / ENTRIES_FILE)
    profiles = sorted(result.profiles.values(), key=lambda p: (p.domain, p.motive))
    write_jsonl((case_profile_to_dict(profile) for profile in profiles), output_dir / CASES_FILE)


def next_step_lines(output_dir: Path) -> list[str]:
    """Qué hacer después de convertir: reconstruir el índice, o antes configurar `.env`.

    Args:
        output_dir: Carpeta donde quedaron los archivos.

    Returns:
        Las líneas a mostrar. Si la carpeta no es la de la base versionada, indica las
        variables de `.env` para probarla sin reemplazar la base v1.
    """
    build = "python run_build_kb_index.py"
    if output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve():
        return [f"Siguiente paso: {build}"]
    folder = output_dir.as_posix()
    return [
        "Para probarla sin reemplazar la base actual, pon en .env:",
        f"  KB_ENTRIES_FILE={folder}/{ENTRIES_FILE}",
        f"  KB_CASES_FILE={folder}/{CASES_FILE}",
        f"  KB_INDEX_DIR={TRIAL_INDEX_DIR}",
        f"y después: {build}",
    ]


def main(argv: list[str]) -> int:
    """Punto de entrada del script: 0 si escribió los archivos, 1 si no."""
    if len(argv) <= SOURCE_ARG:
        print(__doc__)
        return 1
    output_dir = Path(argv[OUTPUT_ARG]) if len(argv) > OUTPUT_ARG else DEFAULT_OUTPUT_DIR
    try:
        result = convert(rows_of_book(read_sheets(Path(argv[SOURCE_ARG]))))
    except (XlsxError, ConversionError) as error:
        print(f"ERROR: {error}")
        return 1
    print("\n".join(report_lines(result)))
    if result.errors:
        print("No se escribió nada: corrige los errores en la hoja y vuelve a ejecutar.")
        return 1
    write_outputs(result, output_dir)
    print(f"Escritos {ENTRIES_FILE} y {CASES_FILE} en {output_dir}")
    print("\n".join(next_step_lines(output_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
