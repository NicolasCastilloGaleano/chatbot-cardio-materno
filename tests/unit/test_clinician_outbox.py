"""Pruebas del reenvío por WhatsApp de los mensajes del profesional (HU-16, ADR 0023, fase 4)."""

import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.inbound.whatsapp.dispatcher import PeriodicTask
from cardio_materno.adapters.outbound.persistence.sqlite_case_repository import (
    SqliteCaseInbox,
    SqliteCaseStore,
)
from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_clinician_outbox import (
    SqliteClinicianOutbox,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_V3,
    SCHEMA_V4,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.clinician_review import ClinicianReview
from cardio_materno.application.conversation_service import ConversationService
from cardio_materno.application.errors import CaseChannelNotSupportedError
from cardio_materno.application.escalation import WAITING_TEXT, EscalationMode
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
)
from cardio_materno.application.incoming_message import IncomingMessage, MessageKind
from cardio_materno.application.outbox_relay import CLINICIAN_LABEL, OutboxRelay
from cardio_materno.application.ports.clinician_outbox import OutboxItem
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.user_conversations import UserConversations
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.escalation import CaseAction, CaseStatus, apply_action
from cardio_materno.domain.user import Channel
from tests.unit.fakes import (
    FakeClock,
    FakeDelayedActions,
    FakeRetriever,
    FakeSender,
    ScriptedAgent,
    SequentialIds,
    make_service,
)
from tests.unit.test_clinician_review import (
    NOW,
    WINDOW,
    Clock,
    review,
    thread_messages,
)
from tests.unit.test_clinician_review import person as register_person
from tests.unit.test_escalation import NOTHING
from tests.unit.test_inquiry_observation import reporting

WA_ID = "573000000001"
CHANNEL_TIME = datetime(2026, 10, 10, 12, 5, tzinfo=UTC)  # cerca del reloj falso del canal


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def whatsapp_person(database: SqliteDatabase, user_id: str = "ana") -> str:
    """Persona de WhatsApp con su caso pendiente y su dirección guardada."""
    case_id = register_person(database, user_id, Channel.WHATSAPP)
    SqliteClinicianOutbox(database).remember(case_id, user_id, WA_ID, NOW)
    return case_id


def whatsapp_review(database: SqliteDatabase, clock: Clock | None = None) -> ClinicianReview:
    base = review(database, clock=clock)
    return ClinicianReview(
        SqliteCaseInbox(database),
        base._threads,  # noqa: SLF001
        base._writer,  # noqa: SLF001
        clock or Clock(),
        SqliteClinicianOutbox(database),
    )


def relay(database: SqliteDatabase, sender: FakeSender, clock: Clock, chars: int = 4096) -> int:
    outbox = SqliteClinicianOutbox(database)
    return OutboxRelay(outbox, sender, SqliteChannelLog(database), chars, clock).run_once()


def addresses(database: SqliteDatabase) -> list[str]:
    return [row["reply_to"] for row in database.query("SELECT reply_to FROM case_addresses")]


# --- Dirección temporal -------------------------------------------------------------------


def test_the_address_is_kept_only_for_an_open_case_the_person_was_told_about(
    database: SqliteDatabase,
) -> None:
    case_id = whatsapp_person(database)
    register_person(database, "beto", Channel.WHATSAPP)
    store = SqliteCaseStore(database).scoped("beto")
    observed = store.open_case()
    assert observed is not None
    store.save(replace(observed, notified=False))
    outbox = SqliteClinicianOutbox(database)

    outbox.remember(observed.id, "beto", "573000000002", NOW)
    outbox.remember(case_id, "beto", "573000000009", NOW)

    assert addresses(database) == [WA_ID]
    assert outbox.reachable(case_id, NOW) and not outbox.reachable(case_id, NOW + WINDOW)


def test_the_address_is_purged_once_the_case_closes_and_nothing_is_pending(
    database: SqliteDatabase,
) -> None:
    case_id = whatsapp_person(database)
    whatsapp_review(database).modify(case_id, "Consulta con tu EPS.")
    sender = FakeSender()

    sent = relay(database, sender, Clock())

    assert sent == 1 and addresses(database) == []
    assert sender.texts_to(WA_ID) == [f"{CLINICIAN_LABEL} Consulta con tu EPS."]


def test_an_expired_case_loses_its_address_and_its_pending_messages(
    database: SqliteDatabase,
) -> None:
    case_id = whatsapp_person(database)
    SqliteClinicianOutbox(database).enqueue(OutboxItem(0, case_id, "ana", "t-ana", "Hola."), NOW)
    sender = FakeSender()

    assert relay(database, sender, Clock(NOW + WINDOW)) == 0
    assert sender.sent == [] and addresses(database) == []
    rows = database.query("SELECT status, error_code, text FROM clinician_outbox")
    assert [tuple(row) for row in rows] == [("fallido", "ventana_cerrada", "")]


# --- Revisión del profesional ---------------------------------------------------------------


def test_a_whatsapp_answer_goes_to_the_thread_and_the_outbox(database: SqliteDatabase) -> None:
    case_id = whatsapp_person(database)

    resolved = whatsapp_review(database).modify(case_id, "Consulta con tu EPS.")

    last = thread_messages(database, "ana")[-1]
    assert resolved.case.status is CaseStatus.MODIFIED
    assert (last.role, last.content) == (Role.CLINICIAN, "Consulta con tu EPS.")
    rows = database.query("SELECT case_id, text, status FROM clinician_outbox")
    assert [tuple(row) for row in rows] == [(case_id, "Consulta con tu EPS.", "pendiente")]


def test_without_an_address_the_clinician_cannot_write_by_whatsapp(
    database: SqliteDatabase,
) -> None:
    case_id = register_person(database, "ana", Channel.WHATSAPP)
    clinician = whatsapp_review(database)

    assert clinician.deliverable(clinician.case(case_id)) is False
    with pytest.raises(CaseChannelNotSupportedError):
        clinician.start_contact(case_id)


def test_direct_contact_by_whatsapp_queues_each_message(database: SqliteDatabase) -> None:
    case_id = whatsapp_person(database)
    clinician = whatsapp_review(database)
    clinician.start_contact(case_id)
    clinician.send_message(case_id, "¿Desde cuándo?")
    sender = FakeSender()

    relay(database, sender, Clock())

    assert sender.texts_to(WA_ID) == [f"{CLINICIAN_LABEL} ¿Desde cuándo?"]
    assert addresses(database) == [WA_ID]


# --- Envío --------------------------------------------------------------------------------


def test_a_long_message_is_split_and_each_part_is_recorded(database: SqliteDatabase) -> None:
    case_id = whatsapp_person(database)
    whatsapp_review(database).modify(case_id, "una respuesta bastante larga para partir")
    sender = FakeSender()

    relay(database, sender, Clock(), chars=20)

    parts = sender.texts_to(WA_ID)
    assert len(parts) > 1 and all(len(part) <= 20 for part in parts)
    kinds = database.query("SELECT kind, thread_id FROM outbound_messages")
    assert {tuple(row) for row in kinds} == {("profesional", "t-ana")}
    assert database.query("SELECT text FROM clinician_outbox")[0]["text"] == ""


def test_a_failed_delivery_is_marked_and_not_retried(database: SqliteDatabase) -> None:
    case_id = whatsapp_person(database)
    whatsapp_review(database).modify(case_id, "Hola.")

    assert relay(database, FakeSender(fail_send=True), Clock()) == 0
    assert relay(database, FakeSender(), Clock()) == 0
    row = database.query("SELECT status, error_code FROM clinician_outbox")[0]
    assert tuple(row) == ("fallido", "envio")


def test_a_message_left_sending_by_a_restart_is_marked_failed(database: SqliteDatabase) -> None:
    case_id = whatsapp_person(database)
    outbox = SqliteClinicianOutbox(database)
    outbox.enqueue(OutboxItem(0, case_id, "ana", "t-ana", "Hola."), NOW)
    outbox.claim(NOW)

    assert outbox.fail_interrupted() == 1
    assert outbox.claim(NOW) == []


def test_a_case_resolved_by_the_inbox_keeps_its_address_until_sent(
    database: SqliteDatabase,
) -> None:
    case_id = whatsapp_person(database)
    outbox = SqliteClinicianOutbox(database)
    outbox.enqueue(OutboxItem(0, case_id, "ana", "t-ana", "Hola."), NOW)
    inbox = SqliteCaseInbox(database)
    found = inbox.get(case_id)
    assert found is not None
    inbox.update_if(apply_action(found.case, CaseAction.APPROVE, NOW), CaseStatus.PENDING)

    outbox.purge(NOW)

    assert outbox.address_of(case_id) == WA_ID


# --- Tarea periódica y esquema ----------------------------------------------------------------


def test_the_periodic_task_keeps_running_after_an_error() -> None:
    calls: list[int] = []
    done = threading.Event()

    def action() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("falla una vez")
        done.set()

    task = PeriodicTask(action, 0.01, "prueba")
    task.start()
    assert done.wait(2)
    task.stop()

    assert len(calls) >= 2


def test_version_4_database_gets_the_address_and_outbox_tables(tmp_path: Path) -> None:
    path = tmp_path / "v4.db"
    connection = sqlite3.connect(path)
    for statement in (*SCHEMA_V1, *SCHEMA_V2, *SCHEMA_V3, *SCHEMA_V4):
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 4")
    connection.commit()
    connection.close()

    database = SqliteDatabase(path)
    tables = {row["name"] for row in database.query("SELECT name FROM sqlite_master")}
    database.close()

    assert {"case_addresses", "clinician_outbox"} <= tables


# --- De punta a punta por WhatsApp ------------------------------------------------------------


def whatsapp_channel(database: SqliteDatabase, sender: FakeSender) -> HandleIncomingMessage:
    """Canal de WhatsApp con escalamiento activo, casos en SQLite y direcciones temporales."""
    clock = FakeClock()
    agent = ScriptedAgent(reporting("r", reported_symptoms=["ardor en el estómago"]))
    options = {"clock": clock, "new_id": SequentialIds(), "escalation": EscalationMode.ACTIVE}

    def factory(
        user_id: str, repository: ThreadRepository, active: str | None, keep_facts: bool
    ) -> Any:
        service = make_service(agent, repository, options, FakeRetriever(NOTHING), active)
        cases = SqliteCaseStore(database).scoped(user_id)
        ports = replace(service._ports, cases=cases)  # noqa: SLF001
        return ConversationService(ports, service._config, active)  # noqa: SLF001

    threads = SqliteUserThreadStore(database)
    conversations = UserConversations(threads, factory, timedelta(hours=12), clock)
    ports = ChannelPorts(
        SqliteUserDirectory(database),
        SqliteChannelLog(database),
        sender,
        FakeDelayedActions(),
        SqliteClinicianOutbox(database),
    )
    config = ChannelConfig(10.0, clock=clock, new_id=lambda: "ana")
    return HandleIncomingMessage(ports, config, conversations)


def test_whatsapp_escalation_contact_and_relay_end_to_end(database: SqliteDatabase) -> None:
    sender = FakeSender()
    channel = whatsapp_channel(database, sender)
    message = IncomingMessage(
        Channel.WHATSAPP, "wamid.1", "hash-ana", WA_ID, MessageKind.TEXT, "text", "me arde"
    )

    channel.handle(message)
    (case_id,) = [row["id"] for row in database.query("SELECT id FROM clinical_cases")]
    clinician = whatsapp_review(database, Clock(CHANNEL_TIME))
    clinician.start_contact(case_id)
    channel.handle(replace(message, channel_message_id="wamid.2", text="sigue el ardor"))
    clinician.send_message(case_id, "¿Tienes fiebre?")
    relay(database, sender, Clock(CHANNEL_TIME))

    assert sender.texts_to(WA_ID) == [WAITING_TEXT, f"{CLINICIAN_LABEL} ¿Tienes fiebre?"]
    assert addresses(database) == [WA_ID]
    assert [m.content for m in thread_messages_of(database, case_id)][-2:] == [
        "sigue el ardor",
        "¿Tienes fiebre?",
    ]


def thread_messages_of(database: SqliteDatabase, case_id: str) -> list[ChatMessage]:
    row = database.query("SELECT user_id, thread_id FROM clinical_cases WHERE id = ?", (case_id,))
    store = SqliteUserThreadStore(database).scoped(row[0]["user_id"])
    return store.all_messages(row[0]["thread_id"])
