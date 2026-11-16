"""Salvaguardas de integración: acceso local, respaldo al migrar, textos pendientes y minimización.

Son regresiones de la verificación integral del 2026-11-16 (ADR 0022 y 0023): fallos que las
pruebas de cada pieza no veían porque aparecen al combinar canales, rutas y configuración.
"""

import itertools
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.inbound.api.local_only import host_name, is_local_request
from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    load_care_access_catalog,
)
from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_VERSION,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.care_access import ADMINISTRATIVE_HEADING, CareAccessActivation
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
)
from cardio_materno.domain.care_access import CareAccessCatalog
from cardio_materno.domain.privacy import redact_identifiers
from tests.unit.fakes import (
    BackingRetriever,
    FakeClock,
    FakeDelayedActions,
    FakeRetriever,
    FakeSender,
    InMemoryThreadRepository,
    ScriptedAgent,
    make_alarm_policy,
    make_service,
    make_user_conversations,
)
from tests.unit.test_care_access import SCENARIOS, Scenario
from tests.unit.test_citizen_view import say, start
from tests.unit.test_handle_incoming_message import ANA, IDLE, text
from tests.unit.test_web_app import build, database

__all__ = ["database"]

REPO = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO / "knowledge" / "care_access.json"
TESTS = REPO / "tests"
TEAM_PATHS = ("/equipo", "/api/chats", "/api/alerts", "/api/config", "/api/chats/x/messages")
CITIZEN_PATHS = ("/", "/api/public/emergency", "/static/equipo.js")
TUNNEL = {"host": "equipo-demo.ngrok-free.app"}
REBOUND = {"host": "sitio-externo.example:8000"}
PROXIED = {"x-forwarded-for": "203.0.113.7"}
WITH_IDENTIFIERS = "mi cédula es 1.000.000.001"


@pytest.fixture(scope="module")
def pending() -> CareAccessCatalog:
    """Catálogo real: todos sus textos están pendientes de aprobación."""
    return load_care_access_catalog(CATALOG_FILE)


def catalog_texts(catalog: CareAccessCatalog) -> list[str]:
    """Todo texto del catálogo que una persona podría llegar a leer."""
    notices = [body for notice in catalog.notices.values() for body in notice.texts.values()]
    questions = [question.text for question in catalog.questions.values()]
    return [ADMINISTRATIVE_HEADING, *notices, *questions]


def assert_shows_no_catalog_text(shown: str, catalog: CareAccessCatalog) -> None:
    for body in catalog_texts(catalog):
        assert body not in shown


# --- La interfaz solo atiende a la propia máquina -------------------------------------------


@pytest.mark.parametrize(
    ("value", "name"),
    [
        ("127.0.0.1:8000", "127.0.0.1"),
        ("LOCALHOST", "localhost"),
        ("http://localhost:8000", "localhost"),
        ("[::1]:8000", "::1"),
        ("http://[::1]:8000", "::1"),
        ("sitio-externo.example:8000", "sitio-externo.example"),
        ("127.0.0.1.sitio-externo.example", "127.0.0.1.sitio-externo.example"),
        ("null", "null"),
        ("", ""),
    ],
)
def test_host_name_drops_scheme_and_port(value: str, name: str) -> None:
    assert host_name(value) == name


def test_a_request_without_host_is_not_local() -> None:
    assert not is_local_request({})
    assert is_local_request({"host": "127.0.0.1:8000", "origin": "http://localhost:8000"})


@pytest.mark.parametrize("headers", [TUNNEL, REBOUND, PROXIED], ids=["tunel", "rebinding", "proxy"])
@pytest.mark.parametrize("path", [*TEAM_PATHS, *CITIZEN_PATHS])
def test_nothing_is_served_to_a_request_from_outside(
    database: SqliteDatabase, headers: dict[str, str], path: str
) -> None:
    harness = build(database)

    response = harness.client.get(path, headers=headers)

    assert response.status_code == 403
    assert "chat" not in response.text and "<html" not in response.text


def test_a_foreign_page_cannot_act_on_the_team_view(database: SqliteDatabase) -> None:
    harness = build(database)
    foreign = {"origin": "https://sitio-externo.example"}

    created = harness.client.post("/api/chats", headers=foreign)
    opaque = harness.client.post("/api/chats", headers={"origin": "null"})

    assert created.status_code == opaque.status_code == 403
    assert database.query("SELECT COUNT(*) FROM users")[0][0] == 0


def test_the_local_browser_still_uses_both_views(database: SqliteDatabase) -> None:
    harness = build(database)
    local = {"origin": "http://127.0.0.1:8000"}

    assert harness.client.get("/equipo").status_code == 200
    assert harness.client.get("/api/alerts", headers=local).status_code == 200
    assert harness.client.post("/api/me/sessions", headers=local).status_code == 201


# --- Respaldo antes de subir el esquema ------------------------------------------------------


def version_2_file(path: Path) -> None:
    connection = sqlite3.connect(path)
    for statement in (*SCHEMA_V1, *SCHEMA_V2):
        connection.execute(statement)
    connection.execute(
        "INSERT INTO users (id, created_at, last_seen_at, consent_status) "
        "VALUES ('ana', '2026-10-01', '2026-10-01', 'pendiente')"
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()


def test_upgrading_keeps_a_copy_that_the_previous_version_can_open(tmp_path: Path) -> None:
    path = tmp_path / "base.db"
    version_2_file(path)

    SqliteDatabase(path).close()

    backup = sqlite3.connect(tmp_path / "base.respaldo-v2.db")
    assert backup.execute("PRAGMA user_version").fetchone()[0] == 2
    assert backup.execute("SELECT id FROM users").fetchall() == [("ana",)]
    columns = {row[1] for row in backup.execute("PRAGMA table_info(users)")}
    backup.close()
    assert "research_consent" not in columns


def test_the_copy_is_made_once_and_never_overwritten(tmp_path: Path) -> None:
    path, backup = tmp_path / "base.db", tmp_path / "base.respaldo-v2.db"
    version_2_file(path)
    SqliteDatabase(path).close()
    before = backup.read_bytes()

    db = SqliteDatabase(path)
    with db.transaction() as connection:
        connection.execute("UPDATE users SET consent_status = 'aceptado'")
    db.close()
    SqliteDatabase(path).close()

    assert backup.read_bytes() == before
    assert sorted(file.name for file in tmp_path.glob("*respaldo*")) == [backup.name]


def test_a_new_database_needs_no_copy(tmp_path: Path) -> None:
    db = SqliteDatabase(tmp_path / "nueva.db")
    version = db.query("PRAGMA user_version")[0][0]
    db.close()
    SqliteDatabase(IN_MEMORY).close()

    assert version == SCHEMA_VERSION
    assert list(tmp_path.glob("*respaldo*")) == []


# --- Un texto pendiente no se muestra por ningún camino --------------------------------------


def active_config(catalog: CareAccessCatalog) -> dict[str, Any]:
    return {
        "alarm_policy": make_alarm_policy(),
        "care_access": catalog,
        "care_access_activation": CareAccessActivation.ACTIVE,
    }


def whatsapp(
    database: SqliteDatabase, agent: ScriptedAgent, catalog: CareAccessCatalog
) -> tuple[HandleIncomingMessage, FakeSender]:
    clock, ids, sender = FakeClock(), itertools.count(1), FakeSender()
    conversations = make_user_conversations(
        agent, SqliteUserThreadStore(database), clock, IDLE, active_config(catalog)
    )
    ports = ChannelPorts(
        SqliteUserDirectory(database), SqliteChannelLog(database), sender, FakeDelayedActions()
    )
    config = ChannelConfig(10.0, clock=clock, new_id=lambda: f"usuario-{next(ids)}")
    return HandleIncomingMessage(ports, config, conversations), sender


def test_the_real_catalog_has_nothing_approved(pending: CareAccessCatalog) -> None:
    assert not any(notice.approved for notice in pending.notices.values())
    assert not any(question.approved for question in pending.questions.values())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_whatsapp_never_sends_a_pending_text(
    database: SqliteDatabase, scenario: Scenario, pending: CareAccessCatalog
) -> None:
    _, message, turn, _ = scenario
    handler, sender = whatsapp(database, ScriptedAgent(turn), pending)

    handler.handle(text(ANA, "m1", message))

    sent = "\n".join(body for _, body in sender.sent)
    stored = "\n".join(row["content"] for row in database.query("SELECT content FROM messages"))
    assert sent
    assert_shows_no_catalog_text(sent + stored, pending)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_the_citizen_view_never_shows_a_pending_text(
    database: SqliteDatabase, scenario: Scenario
) -> None:
    _, message, turn, _ = scenario
    harness = build(database, turn, care_access=True, pending_texts=True)
    session = start(harness)["session"]

    body = say(harness, session, message).json()
    history = harness.client.get(f"/api/me/sessions/{session}/messages").json()

    assert body["access_notice"] is None
    assert all(item["access_notice"] is None for item in history["messages"])
    shown = body["reply"] + json.dumps(history, ensure_ascii=False)
    assert_shows_no_catalog_text(shown, load_care_access_catalog(CATALOG_FILE))


def test_the_fixed_alarm_message_carries_no_pending_text_when_the_model_fails(
    pending: CareAccessCatalog,
) -> None:
    agent = ScriptedAgent(LanguageModelError("sin respuesta"))
    service = make_service(
        agent, InMemoryThreadRepository(), active_config(pending), BackingRetriever(agent)
    )

    result = service.send("tengo la presión alta y no tengo eps ni plata para la cita")

    assert result.alerts
    assert_shows_no_catalog_text(result.reply, pending)


def test_a_model_failure_without_alarm_still_saves_nothing(pending: CareAccessCatalog) -> None:
    repository = InMemoryThreadRepository()
    agent = ScriptedAgent(LanguageModelError("sin respuesta"))
    service = make_service(agent, repository, active_config(pending), FakeRetriever())

    with pytest.raises(LanguageModelError):
        service.send("no tengo eps y no me dan la cita")

    assert repository.list_threads() == []


def test_the_team_can_read_a_pending_text_but_it_is_marked_as_not_shown(
    database: SqliteDatabase,
) -> None:
    _, message, turn, _ = SCENARIOS[2]
    harness = build(database, turn, care_access=True, pending_texts=True)
    chat = harness.client.post("/api/chats").json()["id"]

    body = harness.client.post(f"/api/chats/{chat}/messages", json={"text": message}).json()

    access = body["turn"]["trace"]["care_access"]
    assert access["pending_approval"] is True and access["applied"] is False


# --- La minimización no altera los mensajes de evaluación ------------------------------------


def strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [found for value in node.values() for found in strings(value)]
    if isinstance(node, list):
        return [found for value in node for found in strings(value)]
    return []


def evaluation_texts() -> list[str]:
    """Frases de alarma, coloquiales, de alcance y de recuperación de todas las baterías."""
    files = [*TESTS.rglob("*.json"), REPO / "knowledge" / "alarm_rules.json"]
    return [
        found for file in files for found in strings(json.loads(file.read_text(encoding="utf-8")))
    ]


def test_minimization_leaves_every_evaluation_phrase_untouched() -> None:
    texts = evaluation_texts()

    changed = [phrase for phrase in texts if redact_identifiers(phrase) != phrase]

    # El único mensaje que cambia es el que trae identificadores inventados a propósito.
    assert len(texts) > 500
    assert len(changed) == 1 and changed[0].startswith(WITH_IDENTIFIERS)


@pytest.mark.parametrize(
    "message",
    [
        "tengo la presión en 160/110 y me duele la cabeza",
        "me tomé la presión 3 veces: 150 95 160 100 155 98",
        "el bebé pesó 3200 gramos y tengo 38 semanas",
        "hemoglobina 7.5 y plaquetas 90.000",
        "plaquetas en 150000",
        "llevo 3 días con fiebre de 39.5",
        "saturación 88 y frecuencia 130",
        "me llamó la atención el dolor en el pecho",
    ],
)
def test_minimization_keeps_health_figures(message: str) -> None:
    assert redact_identifiers(message) == message


# --- Retirar la aceptación desde la vista ciudadana ------------------------------------------


def test_withdrawing_the_consent_stops_the_attention_and_the_research_use(
    database: SqliteDatabase,
) -> None:
    _, message, turn, _ = SCENARIOS[3]
    harness = build(database, turn, consent_required=True, care_access=True)
    session = start(harness)["session"]
    base = f"/api/me/sessions/{session}"
    harness.client.post(f"{base}/consent", json={"accepted": True})
    harness.client.post(f"{base}/research", json={"accepted": True})
    assert say(harness, session, message).status_code == 200

    withdrawn = harness.client.post(f"{base}/consent", json={"accepted": False}).json()

    assert (withdrawn["consent"], withdrawn["research"]) == ("rechazado", "rechazado")
    assert say(harness, session, message).status_code == 403
    assert database.query("SELECT COUNT(*) FROM messages")[0][0] == 2
