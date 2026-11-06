"""Pruebas del informe de vacíos de la base (HU-15, B-032)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.report_gaps import main

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    SqliteThreadRepository,
)
from cardio_materno.application.grounded_reply import ABSTENTION_TEXT, CLOSING_TEXT
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread
from cardio_materno.domain.trace import InquiryTrace, ReplyTrace, TurnMode

OLD = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
NEW = datetime(2026, 11, 5, 15, 0, tzinfo=UTC)
PERSON = "me llamo Ana y me arde el estómago"


def trace(query: str, category: str, score: float) -> ReplyTrace:
    inquiry = InquiryTrace(TurnMode.ABSTAIN, best_score=score, top_category=category)
    return ReplyTrace(search_query=query, best_score=score, inquiry=inquiry)


def make_database(path: Path) -> None:
    database = SqliteDatabase(path)
    repo = SqliteThreadRepository(database, None)
    repo.save_thread(open_thread("hilo-1", Domain.CARDIOVASCULAR, "Ardor.", OLD))
    turns = [
        (OLD, ABSTENTION_TEXT, trace("dolor en el brazo", "Dolor torácico", 0.46)),
        (NEW, ABSTENTION_TEXT, trace("ardor en el estómago", "Dolor torácico", 0.55)),
        (NEW, ABSTENTION_TEXT, trace("ardor en el estómago", "Dolor torácico", 0.55)),
        (NEW, CLOSING_TEXT, trace("comida y presión", "Presión arterial", 0.52)),
        (NEW, "DASH es un patrón alimentario.", trace("dash", "Presión arterial", 0.7)),
    ]
    for moment, reply, reply_trace in turns:
        repo.append_message(ChatMessage(Role.USER, PERSON, "hilo-1", moment))
        repo.append_message(ChatMessage(Role.ASSISTANT, reply, "hilo-1", moment, reply_trace))
    database.close()


def report(db: Path, capsys: pytest.CaptureFixture[str], *args: str) -> str:
    assert main(["--db", str(db), *args]) == 0
    return capsys.readouterr().out


def test_the_report_groups_gaps_by_category_without_personal_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "base.db"
    make_database(db)

    out = report(db, capsys)

    assert "Turnos sin orientación: 4 · Categorías: 2" in out
    assert out.index("## Dolor torácico · 3 turnos") < out.index("## Presión arterial · 1 turnos")
    assert "| ardor en el estómago | 2 | sin información | 0.55 |" in out
    assert "| comida y presión | 1 | cierre de la indagación | 0.52 |" in out
    assert "dash" not in out and "Ana" not in out and "hilo-1" not in out


def test_since_keeps_only_the_newer_replies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "base.db"
    make_database(db)

    out = report(db, capsys, "--since", "2026-11-01 00:00")

    assert "Turnos sin orientación: 3" in out and "dolor en el brazo" not in out


def test_a_missing_database_returns_an_error(tmp_path: Path) -> None:
    assert main(["--db", str(tmp_path / "no-existe.db")]) == 1
