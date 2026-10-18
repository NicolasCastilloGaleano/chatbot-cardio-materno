"""Pruebas del chat directo de consola y web sobre SQLite (HU-10, ADR 0016)."""

import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

import pytest

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
from cardio_materno.application.direct_chat import DirectChat, open_console_session
from cardio_materno.application.errors import ChatNotFoundError, ChatReadOnlyError
from cardio_materno.domain.conversation import ThreadStatus
from cardio_materno.domain.user import Channel, ChatLock, new_user
from tests.unit.fakes import (
    FakeClock,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    make_service,
    make_user_conversations,
)

IDLE = timedelta(hours=12)


@dataclass
class DirectHarness:
    chat: DirectChat
    agent: ScriptedAgent
    clock: FakeClock
    store: SqliteUserThreadStore


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def build(database: SqliteDatabase, *turns: dict[str, object] | Exception) -> DirectHarness:
    agent, clock, ids = ScriptedAgent(*turns), FakeClock(), itertools.count(1)
    store = SqliteUserThreadStore(database)
    conversations = make_user_conversations(agent, store, clock, IDLE)
    users = SqliteUserDirectory(database)
    chat = DirectChat(users, conversations, clock, lambda: f"chat-{next(ids)}", lambda: "tok")
    return DirectHarness(chat, agent, clock, store)


def statuses(harness: DirectHarness, user_id: str) -> list[ThreadStatus]:
    return sorted(thread.status for thread in harness.store.scoped(user_id).list_threads())


def test_web_chat_gets_the_same_context_as_a_classic_console_session(
    database: SqliteDatabase,
) -> None:
    turns = (agent_json("r1", summary="acidez"), agent_json("r2", summary="acidez y dieta"))
    harness = build(database, *turns)
    reference = ScriptedAgent(*turns)
    console = make_service(reference, InMemoryThreadRepository())
    web_chat = harness.chat.start(Channel.WEB)

    for text in ("tengo acidez", "¿qué como?"):
        console.send(text)
        harness.chat.send(web_chat, text)

    assert context_of(harness.agent) == context_of(reference)
    assert statuses(harness, web_chat) == [ThreadStatus.OPEN]


def context_of(agent: ScriptedAgent) -> list[list[tuple[str, str, str | None]]]:
    """Lo que recibió el agente en cada llamada (sin las marcas de tiempo del reloj falso)."""
    calls = agent.calls + agent.responder.calls
    return [[(str(m.role), m.content, m.thread_id) for m in call] for call in calls]


def test_only_console_and_web_can_start_direct_chats(database: SqliteDatabase) -> None:
    harness = build(database)

    with pytest.raises(ValueError):
        harness.chat.start(Channel.WHATSAPP)
    assert harness.chat.start(Channel.CONSOLE) == "chat-1"


def test_whatsapp_chat_cannot_be_written_from_the_interface(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"))
    SqliteUserDirectory(database).register(
        new_user("wa", harness.clock()), Channel.WHATSAPP, "hash"
    )

    with pytest.raises(ChatReadOnlyError) as raised:
        harness.chat.send("wa", "hola")

    assert raised.value.reason == ChatLock.CHANNEL
    assert harness.agent.calls == []


def test_console_chat_is_locked_for_the_web_until_the_console_ends(
    database: SqliteDatabase,
) -> None:
    harness = build(database, agent_json("r-consola"), agent_json("r-web"))
    session = open_console_session(harness.chat)

    session.send("tengo acidez")
    with pytest.raises(ChatReadOnlyError) as raised:
        harness.chat.send(session.user_id, "desde la web")
    session.end_session()
    harness.chat.send(session.user_id, "desde la web")

    assert raised.value.reason == ChatLock.LIVE_CONSOLE
    assert len(harness.agent.calls) == 2


def test_console_end_closes_the_open_thread(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"))
    session = open_console_session(harness.chat)

    session.send("tengo acidez")
    session.end_session()

    assert statuses(harness, session.user_id) == [ThreadStatus.CLOSED]


def test_abandoned_console_chat_can_be_released(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"))
    session = open_console_session(harness.chat)

    harness.chat.release_console(session.user_id)
    harness.chat.send(session.user_id, "sigo desde la web")

    assert len(harness.agent.calls) == 1


def test_idle_rule_applies_to_direct_chats(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"), agent_json("r2"))
    chat = harness.chat.start(Channel.WEB)

    harness.chat.send(chat, "tengo acidez")
    harness.clock.current += IDLE + timedelta(minutes=1)
    harness.chat.send(chat, "otra consulta")

    assert statuses(harness, chat) == [ThreadStatus.OPEN, ThreadStatus.CLOSED]


def test_unknown_chat_is_reported(database: SqliteDatabase) -> None:
    harness = build(database)

    with pytest.raises(ChatNotFoundError):
        harness.chat.send("no-existe", "hola")
