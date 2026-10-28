"""Pruebas del script que exporta las conversaciones con su traza."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.export_traces import main

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    SqliteThreadRepository,
)
from cardio_materno.domain.alarms import Alert, AlertOrigin, Severity
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread
from cardio_materno.domain.trace import (
    EvidenceRef,
    GroundingCheck,
    InquiryTrace,
    ReplyTrace,
    RetrievalStatus,
    TurnMode,
)

NOW = datetime(2026, 10, 27, 23, 0, tzinfo=UTC)
TRACE = ReplyTrace(
    reported_symptoms=("fiebre en el bebé",),
    evidence=(EvidenceRef("E1", "k1", 0.68, "Infantil — fiebre"),),
    cited_evidence=("E1",),
    retrieval_status=RetrievalStatus.SUFFICIENT,
    best_score=0.68,
    scope="en_alcance",
    grounding=GroundingCheck(0, 2, True, ("Dale acetaminofén.",), 2, 4),
    search_query="fiebre en el bebé",
    reminded_rules=("RN-MI-13",),
    inquiry=InquiryTrace(TurnMode.INQUIRE, 1, 0, 0.55, 0.03, 2, "Fiebre", None, True),
)


def make_database(path: Path) -> None:
    database = SqliteDatabase(path)
    repo = SqliteThreadRepository(database, None)
    repo.save_thread(open_thread("hilo-abc-123", Domain.MATERNAL_CHILD, "Bebé con fiebre.", NOW))
    repo.append_message(ChatMessage(Role.USER, "mi bebé tiene fiebre", "hilo-abc-123", NOW))
    repo.append_message(ChatMessage(Role.ASSISTANT, "¿Desde cuándo?", "hilo-abc-123", NOW, TRACE))
    alert = Alert(("RN-MI-13",), Severity.IMMEDIATE, AlertOrigin.AGENT, NOW)
    repo.append_alert("hilo-abc-123", alert)
    database.close()


def test_export_shows_messages_trace_alerts_and_inquiry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "base.db"
    make_database(db)

    assert main(["--db", str(db), "--thread", "hilo-abc"]) == 0

    report = capsys.readouterr().out
    assert "## Hilo hilo-abc · sin canal · materno_infantil · abierto" in report
    assert "Alerta RN-MI-13" in report and "mi bebé tiene fiebre" in report
    assert "evidencia: E1 0.68 Infantil — fiebre · citas: E1" in report
    assert "literal (2/4 frases del registro) · descartadas: Dale acetaminofén." in report
    assert "recordatorio de: RN-MI-13" in report
    assert "indagación observada: indagar · turno 1 · s1 0.55" in report


def test_filters_by_local_time_and_last(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "base.db"
    make_database(db)

    main(["--db", str(db), "--since", "2099-01-01 00:00"])
    later = capsys.readouterr().out
    main(["--db", str(db), "--last", "1"])
    last = capsys.readouterr().out

    assert "(0 hilos)" in later and "(1 hilos)" in last


def test_missing_database_returns_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--db", str(tmp_path / "no-existe.db")]) == 1
    assert "No existe la base" in capsys.readouterr().err
