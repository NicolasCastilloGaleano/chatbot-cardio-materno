"""Pruebas de la exportación de la hoja (CSV) a `entries.jsonl`."""

import csv
import json
from pathlib import Path

import pytest
from scripts.export_sheet_kb import SheetFormatError, compute_id, main, to_entries

HEADER = ["Categoría", "Enfoque", "Preguntas", "Respuestas"]
# Id de un registro real de la base, calculado por `kb_sync` en el piloto.
KNOWN_ID = "977166a00ed50636118bd74b7414ecc2d04daf8ed72fd2288b0dde376ca2cdf9"


def write_csv(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return path


def test_id_matches_kb_sync_for_an_existing_entry() -> None:
    entries = [
        json.loads(line)
        for line in Path("knowledge/kb/entries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    entry = next(e for e in entries if e["id"] == KNOWN_ID)

    assert (
        compute_id(entry["domain"], entry["category"], entry["question"], entry["answer"])
        == KNOWN_ID
    )


def test_rows_are_cleaned_deduplicated_and_skipped_when_empty() -> None:
    rows = [
        HEADER,
        ["C", "Solucionar", "  ¿Qué  hago? ", "Respuesta  uno."],
        ["C", "Solucionar", "¿Qué hago?", "Respuesta uno."],
        ["C", "Indagar", "", "Sin pregunta."],
    ]

    entries = to_entries("cardiovascular", rows)

    assert len(entries) == 1
    assert entries[0]["question"] == "¿Qué hago?"
    assert entries[0]["answer"] == "Respuesta uno."


def test_missing_column_raises_error() -> None:
    with pytest.raises(SheetFormatError, match="answer"):
        to_entries("cardiovascular", [["Categoría", "Preguntas"], ["C", "¿P?"]])


def test_main_writes_both_domains_sorted(tmp_path: Path) -> None:
    cardio = write_csv(
        tmp_path / "cv.csv",
        [HEADER, ["B", "Solucionar", "¿P2?", "R2."], ["A", "Indagar", "¿P1?", "R1."]],
    )
    maternal = write_csv(tmp_path / "mi.csv", [HEADER, ["M", "Solucionar", "¿P3?", "R3."]])
    output = tmp_path / "entries.jsonl"

    assert main(["script", str(cardio), str(maternal), str(output)]) == 0

    exported = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [(e["domain"], e["category"]) for e in exported] == [
        ("cardiovascular", "A"),
        ("cardiovascular", "B"),
        ("materno_infantil", "M"),
    ]
