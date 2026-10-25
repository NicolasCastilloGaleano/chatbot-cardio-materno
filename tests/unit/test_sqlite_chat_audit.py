"""Pruebas de la lectura de chats para la auditoría (HU-10, ADR 0016)."""

import itertools
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
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
from cardio_materno.application.direct_chat import DirectChat
from cardio_materno.application.ports.channel_log import InboundEvent, InboundStatus
from cardio_materno.domain.conversation import Role
from cardio_materno.domain.user import Channel
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeClock,
    ScriptedAgent,
    agent_json,
    make_alarm_policy,
    make_user_conversations,
)


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def direct_chat(database: SqliteDatabase, agent: ScriptedAgent) -> DirectChat:
    clock, ids = FakeClock(), itertools.count(1)
    conversations = make_user_conversations(
        agent,
        SqliteUserThreadStore(database),
        clock,
        service_config={"alarm_policy": make_alarm_policy()},
    )
    return DirectChat(
        SqliteUserDirectory(database), conversations, clock, lambda: f"chat-{next(ids)}"
    )


def test_page_returns_most_recent_messages_and_pages_back_without_gaps(
    database: SqliteDatabase,
) -> None:
    agent = ScriptedAgent(*(agent_json(f"r{n}") for n in range(1, 6)))
    chat = direct_chat(database, agent)
    user = chat.start(Channel.WEB)
    for n in range(1, 6):
        chat.send(user, f"p{n}")
    audit = SqliteChatAudit(database)

    first = audit.message_page(user, None, 4)
    second = audit.message_page(user, first.next_before, 4)
    third = audit.message_page(user, second.next_before, 4)

    contents = [e.message.content for page in (third, second, first) for e in page.entries]
    assert contents == [text for n in range(1, 6) for text in (f"p{n}", f"r{n}")]
    assert third.next_before is None
    assert [e.message.content for e in first.entries] == ["p4", "r4", "p5", "r5"]


def test_entries_carry_their_thread_and_turn_alerts(database: SqliteDatabase) -> None:
    agent = ScriptedAgent(agent_json("r1"), agent_json("r2", "nuevo", "cardiovascular", "tensión"))
    chat = direct_chat(database, agent)
    user = chat.start(Channel.WEB)
    chat.send(user, "tengo acidez")
    chat.send(user, "otra cosa")
    chat.send(user, "tengo sangrado vaginal")

    entries = SqliteChatAudit(database).message_page(user, None, 10).entries

    threads = [entry.thread.id for entry in entries]
    assert threads[0] == threads[1] != threads[2] == threads[3]
    urgent = entries[-1]
    assert urgent.message.role is Role.ASSISTANT and urgent.message.content == URGENT_MESSAGE
    assert [alert.rule_ids for alert in urgent.alerts] == [("T-URG",)]
    assert entries[-2].alerts == ()


def test_messages_after_returns_only_new_messages(database: SqliteDatabase) -> None:
    agent = ScriptedAgent(agent_json("r1"), agent_json("r2"))
    chat = direct_chat(database, agent)
    user = chat.start(Channel.WEB)
    chat.send(user, "p1")
    audit = SqliteChatAudit(database)
    last_seen = audit.message_page(user, None, 10).entries[-1].seq

    chat.send(user, "p2")

    new = audit.messages_after(user, last_seen, 10)
    assert [e.message.content for e in new.entries] == ["p2", "r2"]


def test_chat_list_is_ordered_filtered_and_counted(database: SqliteDatabase) -> None:
    agent = ScriptedAgent(agent_json("r1"))
    chat = direct_chat(database, agent)
    console = chat.start(Channel.CONSOLE)
    web = chat.start(Channel.WEB)
    chat.send(console, "hola desde consola")
    audit = SqliteChatAudit(database)

    chats = audit.list_chats(None, 10, 0)

    assert [summary.user_id for summary in chats] == [console, web]
    assert (chats[0].message_count, chats[0].has_open_thread) == (2, True)
    assert [s.user_id for s in audit.list_chats(Channel.WEB, 10, 0)] == [web]
    assert audit.list_chats(None, 1, 1)[0].user_id == web
    summary = audit.get_chat(web)
    assert summary is not None and summary.channel is Channel.WEB
    assert audit.get_chat("no-existe") is None


def test_pending_inbound_counts_messages_still_in_process(database: SqliteDatabase) -> None:
    chat = direct_chat(database, ScriptedAgent())
    user = chat.start(Channel.WEB)
    log = SqliteChannelLog(database)
    now = datetime(2026, 10, 18, tzinfo=UTC)
    for message_id in ("w1", "w2"):
        log.register_inbound(InboundEvent(Channel.WHATSAPP, message_id, user, "text", now))
    log.mark_inbound(Channel.WHATSAPP, "w2", InboundStatus.ANSWERED)

    assert SqliteChatAudit(database).pending_inbound(user) == 1
