"""Pruebas de la persistencia SQLite por usuario (ADR 0015, HU-09)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SCHEMA_VERSION,
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.ports.channel_log import (
    InboundEvent,
    InboundStatus,
    OutboundKind,
    OutboundRecord,
)
from cardio_materno.domain.conversation import (
    ChatMessage,
    Domain,
    Role,
    close_thread,
    open_thread,
)
from cardio_materno.domain.user import Channel, ConsentStatus, new_user, seen_user

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    directory = SqliteUserDirectory(db)
    directory.register(new_user("ana", NOW), Channel.WHATSAPP, "hash-ana")
    directory.register(new_user("beto", NOW), Channel.WHATSAPP, "hash-beto")
    yield db
    db.close()


# --- Aislamiento entre usuarios ------------------------------------------------------


def test_a_user_never_sees_threads_or_messages_of_another(database: SqliteDatabase) -> None:
    store = SqliteUserThreadStore(database)
    ana, beto = store.scoped("ana"), store.scoped("beto")
    ana.save_thread(open_thread("t-ana", Domain.MATERNAL_CHILD, "acidez", NOW))
    ana.append_message(ChatMessage(Role.USER, "tengo acidez", "t-ana", NOW))

    assert beto.get_thread("t-ana") is None
    assert beto.recent_messages("t-ana", 10) == []
    assert beto.all_messages("t-ana") == []
    assert beto.list_threads() == []
    assert [thread.id for thread in ana.list_threads()] == ["t-ana"]


def test_a_user_cannot_write_into_another_users_thread(database: SqliteDatabase) -> None:
    store = SqliteUserThreadStore(database)
    thread = open_thread("t-ana", Domain.MATERNAL_CHILD, "acidez", NOW)
    store.scoped("ana").save_thread(thread)
    beto = store.scoped("beto")

    with pytest.raises(KeyError):
        beto.append_message(ChatMessage(Role.USER, "intruso", "t-ana", NOW))
    with pytest.raises(KeyError):
        beto.save_thread(close_thread(thread, NOW))

    assert store.scoped("ana").get_thread("t-ana") == thread


def test_only_one_open_thread_per_user(database: SqliteDatabase) -> None:
    ana = SqliteUserThreadStore(database).scoped("ana")
    ana.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW))

    with pytest.raises(sqlite3.IntegrityError):
        ana.save_thread(open_thread("t2", Domain.CARDIOVASCULAR, "s", NOW))


def test_closing_before_opening_allows_a_new_thread(database: SqliteDatabase) -> None:
    store = SqliteUserThreadStore(database)
    ana = store.scoped("ana")
    first = open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW)
    ana.save_thread(first)

    ana.save_thread(close_thread(first, NOW))
    ana.save_thread(open_thread("t2", Domain.CARDIOVASCULAR, "s", NOW))

    active = store.open_thread("ana")
    assert active is not None and active.thread.id == "t2"


# --- Hilo abierto y última actividad --------------------------------------------------


def test_open_thread_is_none_without_open_threads(database: SqliteDatabase) -> None:
    store = SqliteUserThreadStore(database)
    thread = open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW)
    store.scoped("ana").save_thread(close_thread(thread, NOW))

    assert store.open_thread("ana") is None
    assert store.open_thread("beto") is None


def test_last_activity_follows_messages_even_without_thread_update(
    database: SqliteDatabase,
) -> None:
    store = SqliteUserThreadStore(database)
    ana = store.scoped("ana")
    ana.save_thread(open_thread("t1", Domain.MATERNAL_CHILD, "s", NOW))
    later = NOW + timedelta(hours=3)

    ana.append_message(ChatMessage(Role.USER, "sigo aquí", "t1", later))

    active = store.open_thread("ana")
    assert active is not None
    assert active.last_activity == later
    assert active.thread.updated_at == NOW


# --- Directorio de usuarios -----------------------------------------------------------


def test_directory_finds_users_by_channel_identity(database: SqliteDatabase) -> None:
    directory = SqliteUserDirectory(database)

    found = directory.find(Channel.WHATSAPP, "hash-ana")

    assert found == new_user("ana", NOW)
    assert directory.find(Channel.WHATSAPP, "desconocido") is None
    assert directory.find(Channel.TELEGRAM, "hash-ana") is None


def test_directory_rejects_a_duplicated_identity(database: SqliteDatabase) -> None:
    with pytest.raises(ValueError):
        SqliteUserDirectory(database).register(new_user("otra", NOW), Channel.WHATSAPP, "hash-ana")

    assert SqliteUserDirectory(database).find(Channel.WHATSAPP, "hash-ana") is not None


def test_directory_saves_last_contact(database: SqliteDatabase) -> None:
    directory = SqliteUserDirectory(database)
    later = NOW + timedelta(days=1)

    directory.save(seen_user(new_user("ana", NOW), later))

    found = directory.find(Channel.WHATSAPP, "hash-ana")
    assert found is not None
    assert found.last_seen_at == later
    assert found.consent_status is ConsentStatus.PENDING
    with pytest.raises(KeyError):
        directory.save(new_user("nadie", NOW))


# --- Registro de mensajes de canal ----------------------------------------------------


def test_inbound_messages_are_deduplicated(database: SqliteDatabase) -> None:
    log = SqliteChannelLog(database)
    event = InboundEvent(Channel.WHATSAPP, "wamid.1", "ana", "text", NOW)

    assert log.register_inbound(event) is True
    assert log.register_inbound(event) is False


def test_inbound_status_can_be_updated_without_storing_text(database: SqliteDatabase) -> None:
    log = SqliteChannelLog(database)
    log.register_inbound(InboundEvent(Channel.WHATSAPP, "wamid.1", "ana", "text", NOW))

    log.mark_inbound(Channel.WHATSAPP, "wamid.1", InboundStatus.FAILED, "modelo")

    row = database.query("SELECT * FROM inbound_events")[0]
    assert (row["status"], row["error_code"]) == ("fallido", "modelo")
    assert set(row.keys()) == {
        "channel",
        "channel_message_id",
        "user_id",
        "kind",
        "status",
        "error_code",
        "received_at",
    }
    with pytest.raises(KeyError):
        log.mark_inbound(Channel.WHATSAPP, "wamid.x", InboundStatus.ANSWERED)


def test_outbound_messages_are_recorded(database: SqliteDatabase) -> None:
    log = SqliteChannelLog(database)

    log.record_outbound(
        OutboundRecord(Channel.WHATSAPP, "ana", OutboundKind.REPLY, "wamid.out", NOW)
    )

    row = database.query("SELECT * FROM outbound_messages")[0]
    assert (row["user_id"], row["kind"], row["thread_id"]) == ("ana", "respuesta", None)


# --- Esquema y transacciones -----------------------------------------------------------


def test_schema_version_is_set_and_data_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "datos" / "cardio.db"
    first = SqliteDatabase(path)
    SqliteUserDirectory(first).register(new_user("ana", NOW), Channel.WHATSAPP, "h")
    first.close()

    second = SqliteDatabase(path)

    assert second.query("PRAGMA user_version")[0][0] == SCHEMA_VERSION
    assert SqliteUserDirectory(second).find(Channel.WHATSAPP, "h") is not None
    second.close()


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cardio.db"
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    connection.close()

    with pytest.raises(DatabaseVersionError):
        SqliteDatabase(path)


def test_failed_transaction_leaves_no_partial_writes(database: SqliteDatabase) -> None:
    with pytest.raises(RuntimeError), database.transaction() as connection:
        connection.execute(
            "INSERT INTO users (id, created_at, last_seen_at, consent_status) "
            "VALUES ('x', 'a', 'a', 'pendiente')"
        )
        raise RuntimeError("falla a mitad")

    assert database.query("SELECT id FROM users WHERE id = 'x'") == []
