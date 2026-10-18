"""Pruebas del caso de uso de los canales de chat continuo (HU-09, ADR 0014 y 0015)."""

import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
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
from cardio_materno.application.channel_messages import (
    MODEL_ERROR_TEXT,
    UNSUPPORTED_MESSAGE_TEXT,
    WAIT_NOTICE_TEXT,
)
from cardio_materno.application.conversation_service import ConversationService
from cardio_materno.application.errors import ChannelDeliveryError, LanguageModelError
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
)
from cardio_materno.application.incoming_message import (
    IncomingMessage,
    MessageKind,
    make_identity_hasher,
)
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.domain.conversation import ThreadStatus
from cardio_materno.domain.user import Channel
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeClock,
    FakeDelayedActions,
    FakeSender,
    ScriptedAgent,
    SequentialIds,
    agent_json,
    make_alarm_policy,
    make_service,
)

ANA, BETO = "573000000001", "573000000002"
IDLE = timedelta(hours=12)
HASH = make_identity_hasher("secreto-de-prueba")


@dataclass
class ChannelHarness:
    """Caso de uso armado con SQLite en memoria y dobles."""

    handler: HandleIncomingMessage
    database: SqliteDatabase
    sender: FakeSender
    delayed: FakeDelayedActions
    clock: FakeClock
    agent: ScriptedAgent

    def status_of(self, message_id: str) -> tuple[str, str | None]:
        row = self.database.query(
            "SELECT status, error_code FROM inbound_events WHERE channel_message_id = ?",
            (message_id,),
        )[0]
        return row["status"], row["error_code"]

    def statuses(self, user_hash: str) -> list[ThreadStatus]:
        user = SqliteUserDirectory(self.database).find(Channel.WHATSAPP, user_hash)
        assert user is not None
        threads = SqliteUserThreadStore(self.database).scoped(user.id).list_threads()
        return sorted(thread.status for thread in threads)


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def build(
    database: SqliteDatabase,
    agent: ScriptedAgent,
    service_config: dict[str, Any] | None = None,
    max_chars: int = 4096,
) -> ChannelHarness:
    clock, thread_ids, user_ids = FakeClock(), SequentialIds(), itertools.count(1)
    sender, delayed = FakeSender(), FakeDelayedActions()
    options = {"clock": clock, "new_id": thread_ids} | (service_config or {})

    def factory(repository: ThreadRepository, active: str | None) -> ConversationService:
        return make_service(agent, repository, options, active_thread_id=active)

    ports = ChannelPorts(
        SqliteUserDirectory(database),
        SqliteUserThreadStore(database),
        SqliteChannelLog(database),
        sender,
        delayed,
    )
    config = ChannelConfig(IDLE, 10.0, max_chars, clock, lambda: f"usuario-{next(user_ids)}")
    handler = HandleIncomingMessage(ports, config, factory)
    return ChannelHarness(handler, database, sender, delayed, clock, agent)


def text(sender: str, message_id: str, body: str) -> IncomingMessage:
    return IncomingMessage(
        Channel.WHATSAPP, message_id, HASH(sender), sender, MessageKind.TEXT, "text", body
    )


def test_first_message_creates_user_and_replies_in_the_same_chat(
    database: SqliteDatabase,
) -> None:
    channel = build(database, ScriptedAgent(agent_json("Orientación sobre acidez")))

    channel.handler.handle(text(ANA, "wamid.1", "tengo 30 semanas y mucha acidez"))

    assert channel.sender.texts_to(ANA) == ["Orientación sobre acidez"]
    assert channel.sender.acknowledged == ["wamid.1"]
    assert channel.status_of("wamid.1") == ("respondido", None)
    assert SqliteUserDirectory(database).find(Channel.WHATSAPP, HASH(ANA)) is not None
    outbound = database.query("SELECT kind, thread_id FROM outbound_messages")
    assert [(row["kind"], row["thread_id"]) for row in outbound] == [("respuesta", "hilo-1")]


def test_the_phone_number_is_never_stored(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r")))

    channel.handler.handle(text(ANA, "wamid.1", "hola"))

    dump = "\n".join(database._connection.iterdump())  # noqa: SLF001 (inspección de la prueba)
    assert ANA not in dump


def test_each_person_gets_only_their_own_reply(database: SqliteDatabase) -> None:
    agent = ScriptedAgent(
        agent_json("r-ana", summary="acidez"),
        agent_json("r-beto", domain="cardiovascular", summary="tensión"),
        agent_json("r-ana-2", summary="acidez y dieta"),
    )
    channel = build(database, agent)

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))
    channel.handler.handle(text(BETO, "wamid.2", "mi papá y su tensión"))
    channel.handler.handle(text(ANA, "wamid.3", "¿qué como?"))

    assert channel.sender.texts_to(ANA) == ["r-ana", "r-ana-2"]
    assert channel.sender.texts_to(BETO) == ["r-beto"]
    third_context = "\n".join(message.content for message in agent.calls[2])
    assert "tensión" not in third_context and "tengo acidez" in third_context


def test_a_repeated_notification_is_not_answered_twice(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1")))

    channel.handler.handle(text(ANA, "wamid.1", "hola"))
    channel.handler.handle(text(ANA, "wamid.1", "hola"))

    assert channel.sender.texts_to(ANA) == ["r1"]
    assert len(channel.agent.calls) == 1


def test_recent_thread_is_resumed(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1"), agent_json("r2")))

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))
    channel.clock.current += IDLE - timedelta(minutes=5)
    channel.handler.handle(text(ANA, "wamid.2", "¿y qué como?"))

    assert channel.statuses(HASH(ANA)) == [ThreadStatus.OPEN]
    assert "tengo acidez" in [message.content for message in channel.agent.calls[1]]


def test_idle_thread_is_closed_before_the_new_message(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1"), agent_json("r2")))

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))
    channel.clock.current += IDLE + timedelta(minutes=1)
    channel.handler.handle(text(ANA, "wamid.2", "hola de nuevo, tengo fiebre"))

    assert channel.statuses(HASH(ANA)) == [ThreadStatus.OPEN, ThreadStatus.CLOSED]
    assert "tengo acidez" not in [message.content for message in channel.agent.calls[1]]


def test_non_text_message_gets_a_notice_without_calling_the_agent(
    database: SqliteDatabase,
) -> None:
    channel = build(database, ScriptedAgent())
    audio = IncomingMessage(
        Channel.WHATSAPP, "wamid.1", HASH(ANA), ANA, MessageKind.UNSUPPORTED, "audio"
    )

    channel.handler.handle(audio)

    assert channel.sender.texts_to(ANA) == [UNSUPPORTED_MESSAGE_TEXT]
    assert channel.agent.calls == []
    assert channel.status_of("wamid.1") == ("ignorado", None)


def test_slow_reply_sends_the_wait_notice_first(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1")))
    channel.delayed.fire = True

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    assert channel.sender.texts_to(ANA) == [WAIT_NOTICE_TEXT, "r1"]
    assert channel.delayed.delays == [10.0]


def test_fast_reply_cancels_the_wait_notice(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1")))

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    assert channel.sender.texts_to(ANA) == ["r1"]
    assert channel.delayed.cancelled == 1


def test_urgency_gets_the_fixed_message_without_the_agent(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(), service_config={"alarm_policy": make_alarm_policy()})

    channel.handler.handle(text(ANA, "wamid.1", "estoy embarazada y tengo sangrado vaginal"))

    assert channel.sender.texts_to(ANA) == [URGENT_MESSAGE]
    assert channel.agent.calls == []
    assert len(database.query("SELECT * FROM alerts")) == 1


def test_model_error_sends_a_clear_message_and_saves_nothing(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(LanguageModelError("Ollama no responde")))

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    assert channel.sender.texts_to(ANA) == [MODEL_ERROR_TEXT]
    assert channel.status_of("wamid.1") == ("fallido", "modelo")
    assert database.query("SELECT * FROM messages") == []


def test_long_reply_is_split_into_several_messages(database: SqliteDatabase) -> None:
    reply = "una respuesta bastante larga para el límite"
    channel = build(database, ScriptedAgent(agent_json(reply)), max_chars=16)

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    parts = channel.sender.texts_to(ANA)
    assert len(parts) > 1 and all(len(part) <= 16 for part in parts)
    assert " ".join(parts) == reply


def test_delivery_failure_marks_the_message_as_failed(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1")))
    channel.sender.fail_send = True

    with pytest.raises(ChannelDeliveryError):
        channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    assert channel.status_of("wamid.1") == ("fallido", "envio")


def test_failed_read_receipt_does_not_block_the_reply(database: SqliteDatabase) -> None:
    channel = build(database, ScriptedAgent(agent_json("r1")))
    channel.sender.fail_acknowledge = True

    channel.handler.handle(text(ANA, "wamid.1", "tengo acidez"))

    assert channel.sender.texts_to(ANA) == ["r1"]
