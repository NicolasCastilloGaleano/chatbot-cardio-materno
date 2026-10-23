"""Pruebas del conversor de la hoja maestra de la base v2 (MIG-06, ADR 0016)."""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from scripts.convert_rag_xlsx import CASES_FILE, ENTRIES_FILE, Column, main
from scripts.xlsx_reader import XlsxError, column_index, read_sheets

from cardio_materno.adapters.outbound.rag.knowledge_files import load_case_profiles, load_entries
from cardio_materno.domain.knowledge import STAGE_FOCUS, STAGE_ROUTE, Stage

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
HEADER = [column.value for column in Column]
SHEET = "MATERNO-INFANTIL"


# --- Libro de Excel sintético -------------------------------------------------------------------


def letters(index: int) -> str:
    text = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        text = chr(ord("A") + rest) + text
    return text


def cell(ref: str, text: str, shared: list[str] | None) -> str:
    if shared is None:
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
    shared.append(text)
    return f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>'


def sheet_xml(rows: list[list[str]], shared: list[str] | None) -> str:
    body = "".join(
        f'<row r="{r}">'
        + "".join(cell(f"{letters(c)}{r}", text, shared) for c, text in enumerate(row) if text)
        + "</row>"
        for r, row in enumerate(rows, start=1)
    )
    return f'<worksheet xmlns="{MAIN}"><sheetData>{body}</sheetData></worksheet>'


def write_xlsx(path: Path, sheets: dict[str, list[list[str]]], use_shared: bool = False) -> Path:
    shared: list[str] | None = [] if use_shared else None
    names = list(sheets)
    with zipfile.ZipFile(path, "w") as book:
        tags = "".join(
            f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)
        )
        book.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>{tags}</sheets></workbook>',
        )
        rels = "".join(
            f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{PACKAGE}">{rels}</Relationships>'
        )
        for i, name in enumerate(names, 1):
            book.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(sheets[name], shared))
        if shared is not None:
            items = "".join(f"<si><t>{escape(text)}</t></si>" for text in shared)
            book.writestr("xl/sharedStrings.xml", f'<sst xmlns="{MAIN}">{items}</sst>')
    return path


def case_rows(motive: str = "colico_lactante", skip: Stage | None = None) -> list[list[str]]:
    rows = []
    for stage in Stage:
        if stage is skip:
            continue
        values = {
            Column.CATEGORY: "Infantil — digestivo",
            Column.FOCUS: STAGE_FOCUS[stage].value,
            Column.QUESTION: f"pregunta de {stage}",
            Column.ANSWER: f"Respuesta de {stage}. ¿Cómo lo ves?",
            Column.MOTIVE: motive,
            Column.STAGE: stage.value,
            Column.ROUTE: STAGE_ROUTE[stage].value,
            Column.CLINICAL_READING: "Sugiere cólico del lactante.",
            Column.DATA_TO_COLLECT: "edad en meses | horario del llanto",
            Column.ESCALATION_SIGNS: "Vómito verde | Fiebre",
            Column.BASE_ROUTE: "autocuidado",
        }
        rows.append([values.get(column, "") for column in Column])
    return rows


def convert(tmp_path: Path, rows: list[list[str]], use_shared: bool = False) -> int:
    book = write_xlsx(tmp_path / "RAG.xlsx", {SHEET: [HEADER, *rows]}, use_shared)
    return main(["script", str(book), str(tmp_path / "salida")])


# --- Lector de .xlsx ----------------------------------------------------------------------------


@pytest.mark.parametrize(("ref", "index"), [("A1", 0), ("N5", 13), ("Z9", 25), ("AB7", 27)])
def test_column_index_from_cell_reference(ref: str, index: int) -> None:
    assert column_index(ref) == index


def test_reader_keeps_empty_cells_in_place_with_inline_and_shared_strings(tmp_path: Path) -> None:
    for use_shared in (False, True):
        book = write_xlsx(tmp_path / f"b{use_shared}.xlsx", {"H": [["a", "", "c"]]}, use_shared)

        assert read_sheets(book) == {"H": [["a", "", "c"]]}


def test_reader_rejects_a_file_that_is_not_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "no.xlsx"
    path.write_text("hola", encoding="utf-8")

    with pytest.raises(XlsxError):
        read_sheets(path)


# --- Conversión ---------------------------------------------------------------------------------


@pytest.mark.parametrize("use_shared", [False, True])
def test_complete_case_is_converted_to_entries_and_case_profile(
    tmp_path: Path, use_shared: bool
) -> None:
    assert convert(tmp_path, case_rows(), use_shared) == 0

    entries = load_entries(tmp_path / "salida" / ENTRIES_FILE)
    profiles = load_case_profiles(tmp_path / "salida" / CASES_FILE)
    assert len(entries) == len(Stage)
    assert entries[0].id == "materno_infantil:colico_lactante:T1_discriminantes"
    assert profiles[0].data_to_collect == ("edad en meses", "horario del llanto")
    assert "Sugiere" not in (tmp_path / "salida" / ENTRIES_FILE).read_text(encoding="utf-8")


def test_case_with_a_missing_stage_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert convert(tmp_path, case_rows(skip=Stage.EMOTIONAL_SUPPORT)) == 1

    assert "apoyo_emocional" in capsys.readouterr().out
    assert not (tmp_path / "salida").exists()


def test_stage_with_the_wrong_focus_is_reported_with_its_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = case_rows()
    rows[0][list(Column).index(Column.FOCUS)] = "Remitir"

    assert convert(tmp_path, rows) == 1
    assert f"{SHEET}, fila 2" in capsys.readouterr().out


def test_case_data_must_match_in_all_its_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = case_rows()
    rows[5][list(Column).index(Column.CLINICAL_READING)] = "Otra lectura."

    assert convert(tmp_path, rows) == 1
    assert "no coinciden" in capsys.readouterr().out


def test_missing_column_or_unknown_sheet_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    no_route = [HEADER[:6] + HEADER[7:]]
    assert convert(tmp_path, [], use_shared=False) == 0  # Hoja vacía: sin registros, sin error.
    book = write_xlsx(tmp_path / "x.xlsx", {SHEET: no_route, "OTRA": [HEADER]})

    assert main(["script", str(book), str(tmp_path / "y")]) == 1
    assert "OTRA" in capsys.readouterr().out


def test_unvalidated_entries_produce_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert convert(tmp_path, case_rows()) == 0

    assert "B-019" in capsys.readouterr().out
