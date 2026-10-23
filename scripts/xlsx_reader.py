"""Lector mínimo de hojas de Excel (`.xlsx`) con la biblioteca estándar (ADR 0017).

Un `.xlsx` es un ZIP con XML: `xl/workbook.xml` lista las hojas, `xl/_rels/workbook.xml.rels`
dice en qué archivo está cada una y `xl/sharedStrings.xml` guarda los textos compartidos (Excel
lo usa al guardar; otras herramientas escriben el texto dentro de la celda). Solo se leen
valores, no fórmulas ni formato.
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELS_PART = "xl/_rels/workbook.xml.rels"
SHARED_STRINGS_PART = "xl/sharedStrings.xml"
XL_DIR = "xl/"
COLUMN_LETTERS = re.compile(r"[A-Z]+")
ALPHABET_SIZE = 26
SHARED_STRING_TYPE = "s"

Rows = list[list[str]]


class XlsxError(ValueError):
    """El archivo no es un `.xlsx` válido o le falta una parte."""


def read_sheets(path: Path) -> dict[str, Rows]:
    """Lee todas las hojas de un libro de Excel.

    Args:
        path: Ruta del archivo `.xlsx`.

    Returns:
        Nombre de la hoja → filas (cada fila, la lista de textos de sus celdas, sin huecos
        a la izquierda: una celda vacía queda como "").

    Raises:
        XlsxError: Si el archivo no existe, no es un ZIP o le faltan partes del libro.
    """
    try:
        with zipfile.ZipFile(path) as book:
            shared = _shared_strings(book)
            return {name: _sheet_rows(book, part, shared) for name, part in _sheet_parts(book)}
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise XlsxError(f"No se pudo leer el libro {path}: {error}") from error


def _sheet_parts(book: zipfile.ZipFile) -> list[tuple[str, str]]:
    """Pares (nombre de la hoja, parte del ZIP) en el orden del libro."""
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in _xml(book, WORKBOOK_RELS_PART).iter(f"{PACKAGE_REL_NS}Relationship")
    }
    sheets = _xml(book, WORKBOOK_PART).iter(f"{MAIN_NS}sheet")
    return [(s.get("name", ""), _part_path(targets[s.get(f"{REL_NS}id")])) for s in sheets]


def _part_path(target: str) -> str:
    """Ruta de la parte dentro del ZIP (los destinos son relativos a `xl/` o absolutos)."""
    return target.lstrip("/") if target.startswith("/") else XL_DIR + target


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    """Textos compartidos del libro (vacío si el libro no los usa)."""
    if SHARED_STRINGS_PART not in book.namelist():
        return []
    return [_text_of(item) for item in _xml(book, SHARED_STRINGS_PART).iter(f"{MAIN_NS}si")]


def _sheet_rows(book: zipfile.ZipFile, part: str, shared: list[str]) -> Rows:
    """Filas de una hoja, con cada celda en la columna que le corresponde."""
    rows: Rows = []
    for row in _xml(book, part).iter(f"{MAIN_NS}row"):
        cells = {column_index(c.get("r", "")): _cell_value(c, shared) for c in row}
        width = max(cells, default=-1) + 1
        rows.append([cells.get(index, "") for index in range(width)])
    return rows


def _cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    """Texto de una celda: compartido, en línea o valor directo."""
    value = cell.find(f"{MAIN_NS}v")
    if cell.get("t") == SHARED_STRING_TYPE and value is not None and value.text:
        return shared[int(value.text)]
    inline = cell.find(f"{MAIN_NS}is")
    if inline is not None:
        return _text_of(inline)
    if value is None:
        return ""
    return value.text or ""


def _text_of(element: ElementTree.Element) -> str:
    """Texto de un elemento con fragmentos `<t>` (texto enriquecido incluido)."""
    return "".join(t.text or "" for t in element.iter(f"{MAIN_NS}t"))


def _xml(book: zipfile.ZipFile, part: str) -> ElementTree.Element:
    """Raíz XML de una parte del libro."""
    return ElementTree.fromstring(book.read(part))


def column_index(reference: str) -> int:
    """Índice (desde 0) de la columna de una referencia de celda ("A1" → 0, "AB7" → 27).

    Raises:
        XlsxError: Si la referencia no empieza con letras de columna.
    """
    match = COLUMN_LETTERS.match(reference)
    if match is None:
        raise XlsxError(f"Referencia de celda inválida: '{reference}'")
    index = 0
    for letter in match.group():
        index = index * ALPHABET_SIZE + ord(letter) - ord("A") + 1
    return index - 1
