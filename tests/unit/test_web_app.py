"""Pruebas de la API web de auditoría multicanal y chat directo (HU-10), sin Ollama."""

import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cardio_materno.adapters.inbound.api.serializers import trace_to_dict
from cardio_materno.adapters.inbound.api.web_app import WebOptions, create_app
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
from cardio_materno.application.direct_chat import DirectChat, open_console_session
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.ports.channel_log import InboundEvent
from cardio_materno.domain.trace import ReplyTrace
from cardio_materno.domain.user import Channel, new_user
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeClock,
    ScriptedAgent,
    agent_json,
    citing,
    knowledge_entry,
    make_alarm_policy,
    make_user_conversations,
    scoped,
)

PAGE_SIZE = 2
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


@dataclass
class WebHarness:
    client: TestClient
    chat: DirectChat
    database: SqliteDatabase


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def build(database: SqliteDatabase, *turns: dict[str, Any] | Exception) -> WebHarness:
    agent, clock, ids = ScriptedAgent(*turns), FakeClock(), itertools.count(1)
    conversations = make_user_conversations(
        agent,
        SqliteUserThreadStore(database),
        clock,
        service_config={"alarm_policy": make_alarm_policy()},
    )
    chat = DirectChat(
        SqliteUserDirectory(database), conversations, clock, lambda: f"chat-{next(ids):04d}"
    )
    entry = knowledge_entry(answer="Orientación validada para la prueba")
    app = create_app(chat, SqliteChatAudit(database), [entry], WebOptions(PAGE_SIZE, 3.0))
    return WebHarness(TestClient(app), chat, database)


def new_web_chat(harness: WebHarness) -> str:
    response = harness.client.post("/api/chats")
    assert response.status_code == 201
    chat_id: str = response.json()["id"]
    return chat_id


def send(harness: WebHarness, chat_id: str, text: str, after: int = 0) -> Any:
    return harness.client.post(
        f"/api/chats/{chat_id}/messages", json={"text": text, "after": after}
    )


def whatsapp_chat(database: SqliteDatabase) -> str:
    SqliteUserDirectory(database).register(new_user("wa-1", NOW), Channel.WHATSAPP, "hash")
    return "wa-1"


# --- Página y configuración -------------------------------------------------------------


def test_page_script_and_config_are_served(database: SqliteDatabase) -> None:
    harness = build(database)

    config = harness.client.get("/api/config").json()

    assert harness.client.get("/").status_code == 200
    assert harness.client.get("/static/app.js").status_code == 200
    assert harness.client.get("/static/../web_app.py").status_code == 404
    assert config["page_size"] == PAGE_SIZE and config["poll_seconds"] == 3.0
    assert {"id": "whatsapp", "label": "WhatsApp"} in config["channels"]


def test_client_implements_the_multichannel_view(database: SqliteDatabase) -> None:
    harness = build(database)

    page = harness.client.get("/").text
    script = harness.client.get("/static/app.js").text
    styles = harness.client.get("/static/styles.css").text

    assert 'id="chat-list"' in page and 'id="channel-filters"' in page
    assert 'id="release-chat"' in page and 'id="audit-panel"' in page
    assert "/api/chats" in script and "before=" in script and "after=" in script
    assert 'event.key !== "Enter" || event.shiftKey || event.isComposing' in script
    assert "Estoy procesando tu mensaje" in script and "setInterval(poll" in script
    assert "textContent" in script and "innerHTML" not in script
    assert "--thread-5" in styles and ".thread-separator" in styles


# --- Chats --------------------------------------------------------------------------------


def test_new_session_creates_an_empty_writable_web_chat(database: SqliteDatabase) -> None:
    harness = build(database)

    chat_id = new_web_chat(harness)

    chat = harness.client.get(f"/api/chats/{chat_id}").json()
    assert chat["channel"] == "web" and chat["writable"] is True and chat["lock"] is None
    assert chat["label"] == f"Web · {chat_id[:8]}"
    assert [c["id"] for c in harness.client.get("/api/chats").json()] == [chat_id]


def test_chat_list_can_be_filtered_by_channel(database: SqliteDatabase) -> None:
    harness = build(database)
    web = new_web_chat(harness)
    whatsapp = whatsapp_chat(database)

    only_whatsapp = harness.client.get("/api/chats", params={"channel": "whatsapp"}).json()

    assert [c["id"] for c in only_whatsapp] == [whatsapp]
    assert {c["id"] for c in harness.client.get("/api/chats").json()} == {web, whatsapp}
    assert harness.client.get("/api/chats", params={"channel": "otro"}).status_code == 422


def test_unknown_chat_is_not_found(database: SqliteDatabase) -> None:
    harness = build(database)

    assert harness.client.get("/api/chats/no-existe").status_code == 404
    assert harness.client.get("/api/chats/no-existe/messages").status_code == 404
    assert send(harness, "no-existe", "hola").status_code == 404


# --- Enviar ---------------------------------------------------------------------------------


def test_sending_returns_the_turn_and_the_persisted_messages_with_full_evidence(
    database: SqliteDatabase,
) -> None:
    harness = build(database, citing(agent_json("Orientación validada para la prueba"), "E1"))
    chat_id = new_web_chat(harness)

    body = send(harness, chat_id, "tengo acidez").json()

    assert body["turn"]["reply"] == "Orientación validada para la prueba"
    reply = body["messages"][-1]
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert reply["seq"] > body["messages"][0]["seq"]
    assert reply["thread"]["status"] == "abierto"
    assert reply["trace"]["evidence"][0]["answer"] == "Orientación validada para la prueba"
    assert body["chat"]["message_count"] == 2


def test_whatsapp_chat_is_read_only_on_the_server(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"))
    chat_id = whatsapp_chat(database)

    response = send(harness, chat_id, "intento escribir")
    chat = harness.client.get(f"/api/chats/{chat_id}").json()

    assert response.status_code == 403
    assert response.json()["detail"] == "Chat de WhatsApp: solo auditoría."
    assert chat["writable"] is False and chat["lock_text"] == "Chat de WhatsApp: solo auditoría."


def test_console_chat_is_locked_until_released(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"))
    session = open_console_session(harness.chat)
    chat_id = session.user_id

    locked = send(harness, chat_id, "desde la web")
    released = harness.client.post(f"/api/chats/{chat_id}/release").json()
    accepted = send(harness, chat_id, "desde la web")

    assert locked.status_code == 403
    assert locked.json()["detail"].startswith("En uso en la consola")
    assert released["writable"] is True
    assert accepted.status_code == 200
    assert harness.client.post(f"/api/chats/{chat_id}/release").status_code == 409


def test_model_failure_is_a_clear_gateway_error(database: SqliteDatabase) -> None:
    harness = build(database, LanguageModelError("detalle interno"))
    chat_id = new_web_chat(harness)

    response = send(harness, chat_id, "Tengo una consulta")

    assert response.status_code == 502
    assert (
        response.json()["detail"] == "No se pudo generar la respuesta. Puedes intentarlo de nuevo."
    )


def test_empty_text_is_rejected(database: SqliteDatabase) -> None:
    harness = build(database)
    chat_id = new_web_chat(harness)

    assert send(harness, chat_id, "   ").status_code == 422


def test_out_of_scope_reply_is_returned_but_not_persisted(database: SqliteDatabase) -> None:
    harness = build(database, scoped(agent_json(), "fuera_de_alcance", "deportes"))
    chat_id = new_web_chat(harness)

    body = send(harness, chat_id, "¿quién ganó el partido?").json()

    assert body["turn"]["out_of_scope"] is True and body["turn"]["thread"] is None
    assert body["messages"] == []


def test_immediate_alarm_is_stored_with_its_alert(database: SqliteDatabase) -> None:
    harness = build(database)
    chat_id = new_web_chat(harness)

    body = send(harness, chat_id, "tengo sangrado vaginal").json()

    reply = body["messages"][-1]
    assert reply["content"] == URGENT_MESSAGE and reply["trace"] is None
    assert reply["alerts"][0]["severity"] == "urgencia_inmediata"


# --- Leer por páginas ---------------------------------------------------------------------


def test_messages_load_newest_first_and_page_backwards(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("r1"), agent_json("r2"))
    chat_id = new_web_chat(harness)
    send(harness, chat_id, "p1")
    send(harness, chat_id, "p2")
    url = f"/api/chats/{chat_id}/messages"

    latest = harness.client.get(url).json()
    older = harness.client.get(url, params={"before": latest["next_before"]}).json()

    assert [m["content"] for m in latest["messages"]] == ["p2", "r2"]
    assert [m["content"] for m in older["messages"]] == ["p1", "r1"]
    assert older["next_before"] is None


def test_polling_after_the_last_seq_returns_only_new_messages_and_pending(
    database: SqliteDatabase,
) -> None:
    harness = build(database, agent_json("r1"), agent_json("r2"))
    chat_id = new_web_chat(harness)
    first = send(harness, chat_id, "p1").json()
    last_seq = first["messages"][-1]["seq"]
    send(harness, chat_id, "p2")
    SqliteChannelLog(database).register_inbound(
        InboundEvent(Channel.WHATSAPP, "wamid.x", chat_id, "text", NOW)
    )

    update = harness.client.get(f"/api/chats/{chat_id}/messages", params={"after": last_seq}).json()

    assert [m["content"] for m in update["messages"]] == ["p2", "r2"]
    assert update["pending"] == 1


def test_trace_includes_the_case_state_of_the_v2_base() -> None:
    trace = ReplyTrace(
        case_motive="fiebre", case_stage="T2_caracterizacion", case_visited=("a", "b")
    )

    snapshot = trace_to_dict(trace, {})["case"]

    assert snapshot == {"motive": "fiebre", "stage": "T2_caracterizacion", "visited": ["a", "b"]}
    assert trace_to_dict(ReplyTrace(), {})["case"] is None
