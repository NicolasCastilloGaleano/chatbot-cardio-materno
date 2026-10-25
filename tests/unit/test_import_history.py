"""Pruebas de la importación de los hilos JSON al chat histórico (HU-10, ADR 0016)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_chat_audit import SqliteChatAudit
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.import_history import import_history
from cardio_materno.domain.alarms import Alert, AlertOrigin, Severity
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread
from cardio_materno.domain.trace import ReplyTrace
from cardio_materno.domain.user import Channel

OLD = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def legacy_threads(tmp_path: Path) -> JsonFileThreadRepository:
    """Dos hilos JSON (uno quedó abierto), creados en desorden, con traza y alerta."""
    source = JsonFileThreadRepository(tmp_path / "threads")
    later = OLD + timedelta(days=1)
    source.save_thread(open_thread("t-nuevo", Domain.CARDIOVASCULAR, "presión", later))
    source.save_thread(open_thread("t-viejo", Domain.MATERNAL_CHILD, "acidez", OLD))
    source.append_message(ChatMessage(Role.USER, "tengo acidez", "t-viejo", OLD))
    trace = ReplyTrace(reported_symptoms=("acidez",))
    source.append_message(ChatMessage(Role.ASSISTANT, "r-acidez", "t-viejo", OLD, trace))
    source.append_message(ChatMessage(Role.USER, "presión alta", "t-nuevo", later))
    source.append_message(ChatMessage(Role.ASSISTANT, "r-presión", "t-nuevo", later))
    alert = Alert(("RN-CV-06",), Severity.PRIORITY, AlertOrigin.USER, later)
    source.append_alert("t-nuevo", alert)
    return source


def run_import(source: JsonFileThreadRepository, database: SqliteDatabase):  # type: ignore[no-untyped-def]
    return import_history(source, SqliteUserDirectory(database), SqliteUserThreadStore(database))


def test_legacy_threads_become_a_read_only_historical_chat(tmp_path: Path) -> None:
    database = SqliteDatabase(IN_MEMORY)

    report = run_import(legacy_threads(tmp_path), database)

    audit = SqliteChatAudit(database)
    entries = audit.message_page(report.user_id, None, 10).entries
    owner = SqliteUserDirectory(database).get(report.user_id)
    assert (report.imported, report.skipped, report.messages) == (2, 0, 4)
    assert owner is not None and owner.channel is Channel.HISTORICAL
    assert [e.message.content for e in entries] == [
        "tengo acidez",
        "r-acidez",
        "presión alta",
        "r-presión",
    ]
    assert all(not entry.thread.is_open for entry in entries)
    assert entries[1].message.trace == ReplyTrace(reported_symptoms=("acidez",))
    assert [a.rule_ids for a in entries[3].alerts] == [("RN-CV-06",)]
    assert owner.user.created_at == OLD
    database.close()


def test_running_the_import_twice_does_not_duplicate(tmp_path: Path) -> None:
    database = SqliteDatabase(IN_MEMORY)
    source = legacy_threads(tmp_path)

    first = run_import(source, database)
    second = run_import(source, database)

    assert second.user_id == first.user_id
    assert (second.imported, second.skipped, second.messages) == (0, 2, 0)
    assert SqliteChatAudit(database).get_chat(first.user_id).message_count == 4  # type: ignore[union-attr]
    database.close()


def test_nothing_to_import_creates_no_chat(tmp_path: Path) -> None:
    database = SqliteDatabase(IN_MEMORY)

    report = run_import(JsonFileThreadRepository(tmp_path / "vacio"), database)

    assert report.user_id is None
    assert SqliteChatAudit(database).list_chats(None, 10, 0) == []
    database.close()
