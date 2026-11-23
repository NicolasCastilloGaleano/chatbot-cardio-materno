"""Pruebas del apartado del profesional en la API web (HU-16, ADR 0022, fases 2 y 3)."""

import itertools
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from cardio_materno.adapters.inbound.api.serializers import Knowledge
from cardio_materno.adapters.inbound.api.web_app import (
    ClinicianAccess,
    WebOptions,
    WebServices,
    create_app,
)
from cardio_materno.adapters.outbound.persistence.sqlite_case_repository import SqliteCaseInbox
from cardio_materno.adapters.outbound.persistence.sqlite_chat_audit import SqliteChatAudit
from cardio_materno.adapters.outbound.persistence.sqlite_database import IN_MEMORY, SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.citizen_chat import CitizenChat, CitizenPolicy
from cardio_materno.application.clinician_draft import ClinicianDraftWriter
from cardio_materno.application.clinician_review import ClinicianReview
from cardio_materno.application.direct_chat import DirectChat
from cardio_materno.domain.user import Channel
from tests.unit.fakes import FakeClock, ScriptedAgent, make_user_conversations
from tests.unit.test_clinician_review import DRAFT, NOTE, NOW, Clock, DraftModel, person

KEY = "clave-de-prueba"
# La interfaz solo atiende peticiones de la propia máquina (local_only.py, ADR 0022 de Juan).
LOCAL_URL = "http://127.0.0.1:8000"
HEADERS = {"X-Clinician-Key": KEY}


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def client(database: SqliteDatabase, with_clinician: bool = True) -> TestClient:
    clock, ids = FakeClock(), itertools.count(1)
    conversations = make_user_conversations(ScriptedAgent(), SqliteUserThreadStore(database), clock)
    users = SqliteUserDirectory(database)
    chat = DirectChat(users, conversations, clock, lambda: f"chat-{next(ids):04d}")
    writer = ClinicianDraftWriter(DraftModel(), "PROMPT DEL BORRADOR")
    review = ClinicianReview(
        SqliteCaseInbox(database), SqliteUserThreadStore(database), writer, Clock(NOW)
    )
    access = ClinicianAccess(review, KEY) if with_clinician else None
    citizen = CitizenChat(chat, users, CitizenPolicy(), clock)
    services = WebServices(chat, citizen, SqliteChatAudit(database), access)
    app = create_app(services, Knowledge(), WebOptions(30, 3.0))
    return TestClient(app, base_url=LOCAL_URL)


def test_without_a_configured_key_the_section_does_not_exist(database: SqliteDatabase) -> None:
    api = client(database, with_clinician=False)

    assert api.get("/api/clinician/cases", headers=HEADERS).status_code == 404
    assert api.get("/medico").status_code == 404


def test_the_api_rejects_a_missing_or_wrong_key(database: SqliteDatabase) -> None:
    api = client(database)

    assert api.get("/api/clinician/cases").status_code == 401
    assert api.get("/api/clinician/cases", headers={"X-Clinician-Key": "otra"}).status_code == 401
    assert api.get("/medico").status_code == 200


def test_the_clinician_reviews_drafts_and_approves_a_case(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    api = client(database)

    listed = api.get("/api/clinician/cases", headers=HEADERS).json()
    detail = api.get(f"/api/clinician/cases/{case_id}", headers=HEADERS).json()
    drafted = api.post(f"/api/clinician/cases/{case_id}/draft", headers=HEADERS).json()
    approved = api.post(f"/api/clinician/cases/{case_id}/approve", headers=HEADERS)

    assert [item["id"] for item in listed] == [case_id]
    assert detail["snapshot"]["query"] == "ardor" and detail["deliverable"] is True
    assert [message["role"] for message in detail["messages"]] == ["user"]
    assert (drafted["draft"], drafted["draft_status"]) == (DRAFT, "listo")
    assert drafted["draft_note"] == NOTE
    assert approved.status_code == 200 and approved.json()["status"] == "aprobada"
    chat = api.get("/api/chats/ana/messages").json()["messages"]
    assert (chat[-1]["role"], chat[-1]["content"]) == ("clinician", DRAFT)
    assert all(NOTE not in message["content"] for message in chat)


def test_approving_without_a_draft_or_twice_is_a_conflict(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    api = client(database)

    early = api.post(f"/api/clinician/cases/{case_id}/approve", headers=HEADERS)
    sent = api.post(
        f"/api/clinician/cases/{case_id}/modify", headers=HEADERS, json={"text": "Hola."}
    )
    again = api.post(
        f"/api/clinician/cases/{case_id}/modify", headers=HEADERS, json={"text": "Otra"}
    )

    assert early.status_code == 409 and sent.status_code == 200
    assert sent.json()["status"] == "modificada" and again.status_code == 409


def test_an_empty_reply_and_an_unknown_case_are_rejected(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    api = client(database)

    empty = api.post(f"/api/clinician/cases/{case_id}/modify", headers=HEADERS, json={"text": ""})
    unknown = api.get("/api/clinician/cases/no-existe", headers=HEADERS)

    assert (empty.status_code, unknown.status_code) == (422, 404)


def test_a_whatsapp_case_without_an_outbox_is_shown_but_not_answerable(
    database: SqliteDatabase,
) -> None:
    case_id = person(database, "ana", Channel.WHATSAPP)
    api = client(database)

    detail = api.get(f"/api/clinician/cases/{case_id}", headers=HEADERS).json()
    sent = api.post(
        f"/api/clinician/cases/{case_id}/modify", headers=HEADERS, json={"text": "Hola."}
    )

    assert detail["deliverable"] is False and sent.status_code == 409


def test_the_clinician_talks_directly_with_the_person(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    api = client(database)
    base = f"/api/clinician/cases/{case_id}"

    early = api.post(f"{base}/messages", headers=HEADERS, json={"text": "Hola."})
    started = api.post(f"{base}/contact", headers=HEADERS).json()
    sent = api.post(f"{base}/messages", headers=HEADERS, json={"text": "¿Desde cuándo?"})
    closed = api.post(f"{base}/close", headers=HEADERS).json()

    assert early.status_code == 409 and started["status"] == "en_contacto"
    assert sent.status_code == 200 and closed["status"] == "cerrada"
    chat = api.get("/api/chats/ana/messages").json()["messages"]
    assert (chat[-1]["role"], chat[-1]["content"]) == ("clinician", "¿Desde cuándo?")
