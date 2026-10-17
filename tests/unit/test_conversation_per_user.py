"""El agente recibe el mismo contexto por usuario que en la consola (HU-09, ADR 0015).

Se usa el servicio real con la persistencia SQLite acotada por usuario: un servicio por
mensaje que retoma el hilo abierto del usuario, como lo hará el canal de WhatsApp.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

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
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.domain.conversation import ChatMessage, ThreadStatus
from cardio_materno.domain.user import Channel, new_user
from tests.unit.fakes import (
    FakeClock,
    InMemoryThreadRepository,
    ScriptedAgent,
    SequentialIds,
    agent_json,
    make_service,
    thread_of,
)

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)


@pytest.fixture
def store() -> Iterator[SqliteUserThreadStore]:
    database = SqliteDatabase(IN_MEMORY)
    directory = SqliteUserDirectory(database)
    for user_id in ("ana", "beto"):
        directory.register(new_user(user_id, NOW), Channel.WHATSAPP, f"hash-{user_id}")
    yield SqliteUserThreadStore(database)
    database.close()


def send_as(
    user_id: str,
    text: str,
    agent: ScriptedAgent,
    store: SqliteUserThreadStore,
    shared: dict[str, Any],
) -> TurnResult:
    """Procesa un mensaje con un servicio nuevo que retoma el hilo abierto del usuario."""
    active = store.open_thread(user_id)
    service = make_service(
        agent, store.scoped(user_id), shared, active_thread_id=active.thread.id if active else None
    )
    return service.send(text)


def contents(context: list[ChatMessage]) -> str:
    """Todo el texto que recibió el agente en una llamada."""
    return "\n".join(message.content for message in context)


def test_interleaved_users_never_share_context(store: SqliteUserThreadStore) -> None:
    agent = ScriptedAgent(
        agent_json("r-ana-1", summary="acidez en el embarazo"),
        agent_json("r-beto-1", domain="cardiovascular", summary="tensión del papá"),
        agent_json("r-ana-2", summary="acidez y dieta"),
        agent_json("r-beto-2", domain="cardiovascular", summary="tensión y control"),
    )
    shared: dict[str, Any] = {"clock": FakeClock(), "new_id": SequentialIds()}

    send_as("ana", "tengo acidez", agent, store, shared)
    send_as("beto", "mi papá tiene la tensión elevada", agent, store, shared)
    ana_2 = send_as("ana", "¿qué puedo comer?", agent, store, shared)
    beto_2 = send_as("beto", "¿cada cuánto la mido?", agent, store, shared)

    ana_context, beto_context = contents(agent.calls[2]), contents(agent.calls[3])
    assert "tengo acidez" in ana_context and "r-ana-1" in ana_context
    assert "tensión" not in ana_context and "r-beto-1" not in ana_context
    assert "mi papá tiene la tensión elevada" in beto_context and "r-beto-1" in beto_context
    assert "acidez" not in beto_context and "r-ana-1" not in beto_context
    assert not ana_2.is_new_thread and not beto_2.is_new_thread
    assert thread_of(ana_2).id != thread_of(beto_2).id


def test_resumed_thread_gets_the_same_context_as_a_console_session(
    store: SqliteUserThreadStore,
) -> None:
    turns = (agent_json("r1", summary="acidez"), agent_json("r2", summary="acidez y dieta"))
    console_agent, channel_agent = ScriptedAgent(*turns), ScriptedAgent(*turns)
    console = make_service(console_agent, InMemoryThreadRepository())
    shared: dict[str, Any] = {"clock": FakeClock(), "new_id": SequentialIds()}

    console.send("tengo acidez")
    console.send("¿qué como?")
    send_as("ana", "tengo acidez", channel_agent, store, shared)
    send_as("ana", "¿qué como?", channel_agent, store, shared)

    assert channel_agent.calls == console_agent.calls
    assert channel_agent.responder.calls == console_agent.responder.calls


def test_new_topic_closes_the_users_thread_and_keeps_one_open(
    store: SqliteUserThreadStore,
) -> None:
    agent = ScriptedAgent(agent_json("r1"), agent_json("r2", "nuevo", "cardiovascular", "presión"))
    shared: dict[str, Any] = {"clock": FakeClock(), "new_id": SequentialIds()}

    first = send_as("ana", "tengo acidez", agent, store, shared)
    second = send_as("ana", "otra cosa, mi papá y su tensión", agent, store, shared)

    threads = {thread.id: thread.status for thread in store.scoped("ana").list_threads()}
    assert threads == {
        thread_of(first).id: ThreadStatus.CLOSED,
        thread_of(second).id: ThreadStatus.OPEN,
    }
