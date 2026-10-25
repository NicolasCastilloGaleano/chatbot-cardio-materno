"""Contrato común de `ThreadRepository`: JSON y SQLite deben comportarse igual (ADR 0015).

Así se garantiza que el agente recibe el mismo contexto con cualquiera de los dos adaptadores.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    SqliteThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.domain.alarms import Alert, AlertOrigin, Severity
from cardio_materno.domain.conversation import (
    ChatMessage,
    Domain,
    Role,
    close_thread,
    open_thread,
)
from cardio_materno.domain.trace import EvidenceRef, ReplyTrace, RetrievalStatus, StageTiming
from cardio_materno.domain.user import Channel, new_user

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture(params=["json", "sqlite_sin_usuario", "sqlite_con_usuario"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[ThreadRepository]:
    if request.param == "json":
        yield JsonFileThreadRepository(tmp_path / "threads")
        return
    database = SqliteDatabase(IN_MEMORY)
    owner = None
    if request.param == "sqlite_con_usuario":
        owner = "u1"
        SqliteUserDirectory(database).register(new_user(owner, NOW), Channel.WHATSAPP, "h1")
    yield SqliteThreadRepository(database, owner)
    database.close()


def test_saved_thread_can_be_read_back(repo: ThreadRepository) -> None:
    thread = open_thread("t1", Domain.CARDIOVASCULAR, "presión alta", NOW)

    repo.save_thread(thread)

    assert repo.get_thread("t1") == thread
    assert repo.get_thread("no-existe") is None


def test_list_threads_orders_by_most_recent_update(repo: ThreadRepository) -> None:
    later = NOW.replace(second=1)
    repo.save_thread(close_thread(open_thread("t1", Domain.CARDIOVASCULAR, "primero", NOW), NOW))
    repo.save_thread(open_thread("t2", Domain.MATERNAL_CHILD, "segundo", later))

    assert [thread.id for thread in repo.list_threads()] == ["t2", "t1"]


def test_all_messages_returns_complete_history(repo: ThreadRepository) -> None:
    repo.save_thread(open_thread("t1", Domain.NONE, "saludo", NOW))
    repo.append_message(ChatMessage(Role.USER, "hola", "t1", NOW))
    repo.append_message(ChatMessage(Role.ASSISTANT, "buenas", "t1", NOW))

    assert [message.content for message in repo.all_messages("t1")] == ["hola", "buenas"]
    assert repo.all_messages("missing") == []


def test_updating_thread_keeps_messages(repo: ThreadRepository) -> None:
    thread = open_thread("t1", Domain.NONE, "saludo", NOW)
    repo.save_thread(thread)
    repo.append_message(ChatMessage(Role.USER, "hola", "t1", NOW))

    repo.save_thread(close_thread(thread, NOW))

    assert repo.recent_messages("t1", 10)[0].content == "hola"
    assert repo.get_thread("t1").is_open is False  # type: ignore[union-attr]


def test_recent_messages_respects_limit_and_order(repo: ThreadRepository) -> None:
    repo.save_thread(open_thread("t1", Domain.NONE, "s", NOW))
    for text in ("a", "b", "c"):
        repo.append_message(ChatMessage(Role.USER, text, "t1", NOW))

    assert [m.content for m in repo.recent_messages("t1", 2)] == ["b", "c"]
    assert repo.recent_messages("t1", 0) == []
    assert repo.recent_messages("otro", 2) == []


def test_append_to_missing_thread_raises_key_error(repo: ThreadRepository) -> None:
    with pytest.raises(KeyError):
        repo.append_message(ChatMessage(Role.USER, "hola", "no-existe", NOW))


def test_alert_on_missing_thread_raises_key_error(repo: ThreadRepository) -> None:
    alert = Alert(("X",), Severity.PRIORITY, AlertOrigin.USER, NOW)

    with pytest.raises(KeyError):
        repo.append_alert("no-existe", alert)


def test_alert_on_existing_thread_is_accepted(repo: ThreadRepository) -> None:
    repo.save_thread(open_thread("t1", Domain.CARDIOVASCULAR, "s", NOW))

    alert = Alert(("RN-CV-01", "RN-CV-02"), Severity.IMMEDIATE, AlertOrigin.AGENT, NOW)

    repo.append_alert("t1", alert)

    assert repo.all_alerts("t1") == [alert]
    assert repo.all_alerts("no-existe") == []


def test_trace_round_trip_only_for_assistant_messages(repo: ThreadRepository) -> None:
    repo.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW))
    trace = ReplyTrace(
        reported_symptoms=("secrecion vaginal rosada",),
        evidence=(EvidenceRef("E1", "k1", 0.71, "Embarazo"),),
        cited_evidence=("E1",),
        retrieval_status=RetrievalStatus.SUFFICIENT,
        best_score=0.71,
        timings=(StageTiming("análisis", 1.2),),
        reported_signs=("SALIDA_LIQUIDO_VAGINAL",),
    )
    repo.append_message(ChatMessage(Role.USER, "me sale agüita", "t1", NOW))
    repo.append_message(ChatMessage(Role.ASSISTANT, "r", "t1", NOW, trace))

    messages = repo.recent_messages("t1", 10)

    assert messages[0].trace is None
    assert messages[1].trace == trace
    assert messages[1].created_at == NOW
