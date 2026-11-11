"""Pruebas de la revisión de borradores de la base (`scripts/check_kb.py`)."""

import csv
from pathlib import Path

from scripts.check_kb import Record, check, load_csv, load_source_ids, main

HEADER = ["Categoría", "Enfoque", "Preguntas", "Respuestas", "Fuente", "Tipo"]
GOOD_ANSWER = "Frase de orientación clara y autocontenida. " * 9  # unos 400 caracteres


def draft(
    question: str,
    *,
    origin: str = "b.csv:2",
    answer: str = GOOD_ANSWER.strip(),
    source: str | None = "OMS-CDSS-2008",
    kind: str | None = "general",
) -> Record:
    return Record(origin, "CV-S1", "Solucionar", question, answer, source, kind)


def test_valid_draft_has_no_errors() -> None:
    report = check([draft("¿Cómo pido una cita sin EPS?")], [], {"OMS-CDSS-2008"})

    assert report.errors == []


def test_dose_short_answer_and_unknown_source_are_errors() -> None:
    record = draft("¿Cuánto tomo?", answer="Toma 500 mg cada día.", source="OTRA")

    report = check([record], [], {"OMS-CDSS-2008"})

    assert any("caracteres" in e for e in report.errors)
    assert any("dosis" in e for e in report.errors)
    assert any("fuera del catálogo" in e for e in report.errors)


def test_repeated_question_is_error_and_similar_is_warning() -> None:
    base = [
        draft("¿Cómo pido una cita médica sin tener EPS?", origin="entries.jsonl:1", source=None)
    ]
    batch = [
        draft("¿cómo pido una cita médica sin tener EPS?"),
        draft("¿Cómo pido una cita médica sin tener EPS ahora?", origin="b.csv:3"),
    ]

    report = check(batch, base, None)

    assert any("repetida" in e for e in report.errors)
    assert any("casi igual" in w for w in report.warnings)


def test_quota_warnings_for_focus_and_general_share() -> None:
    batch = [draft(f"¿Pregunta número {i}?", kind="escenario") for i in range(5)]

    report = check(batch, [], None)

    assert any("Solucionar" in w for w in report.warnings)
    assert any("generales" in w for w in report.warnings)


def test_inherited_base_skips_length_and_source_checks() -> None:
    record = draft("¿Pregunta heredada?", answer="Respuesta corta.", source=None, kind=None)

    assert check([record], [], {"X"}).errors == []


def test_csv_and_catalog_are_read(tmp_path: Path) -> None:
    path = tmp_path / "CV-S1.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(
            [HEADER, ["CV-S1", "Solucionar", "¿P?", "R.", "A-1", "general"]]
        )
    catalog = tmp_path / "fuentes.md"
    catalog.write_text(
        "| id | título |\n|---|---|\n| `OMS-CDSS-2008` | Comisión |\n", encoding="utf-8"
    )

    records = load_csv(path)

    assert records[0].source == "A-1" and records[0].kind == "general"
    assert load_source_ids(catalog) == {"OMS-CDSS-2008"}
    assert main([str(path), "--base", str(tmp_path / "no.jsonl"), "--sources", str(catalog)]) == 1
