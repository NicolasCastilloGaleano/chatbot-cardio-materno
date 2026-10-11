"""Pruebas del repositorio de hilos en archivos JSON."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.domain.alarms import Alert, AlertOrigin, Severity
from cardio_materno.domain.conversation import (
    ChatMessage,
    Domain,
    Role,
    close_thread,
    open_thread,
)
from cardio_materno.domain.trace import EvidenceRef, ReplyTrace, RetrievalStatus, StageTiming

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def make_repo(tmp_path: Path) -> JsonFileThreadRepository:
    return JsonFileThreadRepository(tmp_path / "threads")


def test_saved_thread_can_be_read_back(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    thread = open_thread("t1", Domain.CARDIOVASCULAR, "presión alta", NOW)

    repo.save_thread(thread)

    assert repo.get_thread("t1") == thread
    assert repo.get_thread("no-existe") is None


def test_file_is_readable_json_with_thread_and_messages(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "acidez", NOW))
    repo.append_message(ChatMessage(Role.USER, "tengo acidez", "t1", NOW))

    data = json.loads((tmp_path / "threads" / "t1.json").read_text(encoding="utf-8"))

    assert data["domain"] == "materno_infantil"
    assert data["status"] == "abierto"
    assert data["messages"] == [
        {
            "thread_id": "t1",
            "role": "user",
            "content": "tengo acidez",
            "created_at": NOW.isoformat(),
        }
    ]


def test_updating_thread_keeps_messages(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    thread = open_thread("t1", Domain.NONE, "saludo", NOW)
    repo.save_thread(thread)
    repo.append_message(ChatMessage(Role.USER, "hola", "t1", NOW))

    repo.save_thread(close_thread(thread, NOW))

    assert repo.recent_messages("t1", 10)[0].content == "hola"
    assert repo.get_thread("t1").is_open is False  # type: ignore[union-attr]


def test_recent_messages_respects_limit_and_order(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.save_thread(open_thread("t1", Domain.NONE, "s", NOW))
    for text in ("a", "b", "c"):
        repo.append_message(ChatMessage(Role.USER, text, "t1", NOW))

    assert [m.content for m in repo.recent_messages("t1", 2)] == ["b", "c"]
    assert repo.recent_messages("t1", 0) == []
    assert repo.recent_messages("otro", 2) == []


def test_append_to_missing_thread_raises_key_error(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        make_repo(tmp_path).append_message(ChatMessage(Role.USER, "hola", "no-existe", NOW))


def test_alerts_are_saved_and_kept_when_thread_is_updated(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    thread = open_thread("t1", Domain.CARDIOVASCULAR, "s", NOW)
    repo.save_thread(thread)

    repo.append_alert("t1", Alert(("RN-CV-01",), Severity.IMMEDIATE, AlertOrigin.AGENT, NOW))
    repo.save_thread(close_thread(thread, NOW))

    data = json.loads((tmp_path / "threads" / "t1.json").read_text(encoding="utf-8"))
    assert data["alerts"] == [
        {
            "rule_ids": ["RN-CV-01"],
            "severity": "urgencia_inmediata",
            "origin": "agente",
            "created_at": NOW.isoformat(),
        }
    ]


def test_alert_on_missing_thread_raises_key_error(tmp_path: Path) -> None:
    alert = Alert(("X",), Severity.PRIORITY, AlertOrigin.USER, NOW)

    with pytest.raises(KeyError):
        make_repo(tmp_path).append_alert("no-existe", alert)


def test_trace_round_trip_only_for_assistant_messages(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW))
    trace = ReplyTrace(
        reported_symptoms=("secrecion vaginal rosada",),
        evidence=(EvidenceRef("E1", "k1", 0.71, "Embarazo"),),
        cited_evidence=("E1",),
        retrieval_status=RetrievalStatus.SUFFICIENT,
        best_score=0.71,
        timings=(StageTiming("análisis", 1.2), StageTiming("respuesta", 3.4)),
        scope="en_alcance",
        scope_reason="consulta de embarazo",
    )
    repo.append_message(ChatMessage(Role.USER, "me sale agüita", "t1", NOW))
    repo.append_message(ChatMessage(Role.ASSISTANT, "r", "t1", NOW, trace))

    data = json.loads((tmp_path / "threads" / "t1.json").read_text(encoding="utf-8"))
    messages = repo.recent_messages("t1", 10)

    assert "trace" not in data["messages"][0]
    assert data["messages"][1]["trace"] == {
        "reported_symptoms": ["secrecion vaginal rosada"],
        "retrieval_status": "suficiente",
        "best_score": 0.71,
        "evidence": [{"label": "E1", "entry_id": "k1", "score": 0.71, "category": "Embarazo"}],
        "evidence_ids": ["E1"],
        "uncited_reply": False,
        "timings": {"análisis": 1.2, "respuesta": 3.4},
        "scope": "en_alcance",
        "scope_reason": "consulta de embarazo",
    }
    assert messages[1].trace == trace
    assert messages[0].trace is None


def test_legacy_reported_symptoms_are_read_as_trace(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    repo.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW))
    path = tmp_path / "threads" / "t1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["messages"] = [
        {
            "thread_id": "t1",
            "role": "assistant",
            "content": "r",
            "created_at": None,
            "reported_symptoms": ["fiebre"],
        }
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    message = repo.recent_messages("t1", 1)[0]

    assert message.trace == ReplyTrace(reported_symptoms=("fiebre",))
