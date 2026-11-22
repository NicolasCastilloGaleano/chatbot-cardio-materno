"""Pruebas de la revisión de casos por el profesional (HU-16, ADR 0022, fase 2)."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_case_repository import (
    SqliteCaseInbox,
    SqliteCaseStore,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import IN_MEMORY, SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.clinician_draft import ClinicianDraftWriter
from cardio_materno.application.clinician_review import ClinicianReview
from cardio_materno.application.errors import (
    CaseChannelNotSupportedError,
    CaseConflictError,
    DraftNotReadyError,
    LanguageModelError,
)
from cardio_materno.application.turn_context import (
    CLINICIAN_PREFIX,
    TurnInput,
    for_model,
    reply_context,
)
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread
from cardio_materno.domain.escalation import (
    CaseSnapshot,
    CaseStatus,
    DraftStatus,
    open_case,
)
from cardio_materno.domain.trace import ModelUsage
from cardio_materno.domain.user import Channel, new_user

NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
WINDOW = timedelta(hours=24)
PERSON_TEXT = "me llamo Ana y me arde el estómago"
DRAFT = "Te recomiendo consultar con tu EPS. Si empeora, acude a urgencias o llama al 123."
SNAPSHOT = CaseSnapshot(
    Domain.CARDIOVASCULAR, "Ardor de estómago.", ("ardor",), (), "ardor", "sin información", "", 0.5
)


@dataclass
class DraftModel:
    """Modelo falso del borrador: devuelve el texto o falla, y guarda lo que recibió."""

    reply: str | Exception = DRAFT
    calls: list[list[ChatMessage]] = field(default_factory=list)

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(list(messages))
        if isinstance(self.reply, Exception):
            raise self.reply
        return {"draft": self.reply}

    def last_usage(self) -> ModelUsage | None:
        return None


@dataclass
class Clock:
    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    yield db
    db.close()


def person(database: SqliteDatabase, user_id: str, channel: Channel = Channel.WEB) -> str:
    """Registra una persona con su hilo y su caso pendiente; devuelve el id del caso."""
    SqliteUserDirectory(database).register(new_user(user_id, NOW), channel, f"hash-{user_id}")
    threads = SqliteUserThreadStore(database).scoped(user_id)
    threads.save_thread(open_thread(f"t-{user_id}", Domain.CARDIOVASCULAR, "", NOW))
    threads.append_message(ChatMessage(Role.USER, PERSON_TEXT, f"t-{user_id}", NOW))
    case_id = f"caso-{user_id}"
    SqliteCaseStore(database).scoped(user_id).save(
        open_case(case_id, f"t-{user_id}", SNAPSHOT, NOW, WINDOW)
    )
    return case_id


def review(
    database: SqliteDatabase, model: DraftModel | None = None, clock: Clock | None = None
) -> ClinicianReview:
    writer = ClinicianDraftWriter(model or DraftModel(), "PROMPT DEL BORRADOR")
    inbox, threads = SqliteCaseInbox(database), SqliteUserThreadStore(database)
    return ClinicianReview(inbox, threads, writer, clock or Clock())


def thread_messages(database: SqliteDatabase, user_id: str) -> list[ChatMessage]:
    return SqliteUserThreadStore(database).scoped(user_id).all_messages(f"t-{user_id}")


# --- Lista y borrador ---------------------------------------------------------------------


def test_only_open_cases_the_person_was_told_about_are_listed(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    person(database, "beto")
    store = SqliteCaseStore(database).scoped("beto")
    observed = store.open_case()
    assert observed is not None
    store.save(replace(observed, notified=False))

    cases = review(database).pending_cases()

    assert [found.case.id for found in cases] == [case_id]
    assert (cases[0].user_id, cases[0].channel) == ("ana", Channel.WEB)


def test_the_draft_is_written_once_from_the_summary_only(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    model = DraftModel()
    clinician = review(database, model)

    first = clinician.prepare_draft(case_id)
    second = clinician.prepare_draft(case_id)

    assert (first.case.draft, first.case.draft_status) == (DRAFT, DraftStatus.READY)
    assert second.case.draft == DRAFT and len(model.calls) == 1
    sent = "\n".join(message.content for message in model.calls[0])
    assert "Ardor de estómago." in sent and PERSON_TEXT not in sent and "Ana" not in sent


def test_a_failed_draft_is_marked_and_cannot_be_approved(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    clinician = review(database, DraftModel(LanguageModelError("sin modelo")))

    assert clinician.prepare_draft(case_id).case.draft_status is DraftStatus.FAILED
    with pytest.raises(DraftNotReadyError):
        clinician.approve(case_id)


# --- Aprobar y modificar ------------------------------------------------------------------


def test_approving_sends_the_draft_as_the_clinician_and_closes_the_case(
    database: SqliteDatabase,
) -> None:
    case_id = person(database, "ana")
    clinician = review(database)
    clinician.prepare_draft(case_id)

    resolved = clinician.approve(case_id)

    last = thread_messages(database, "ana")[-1]
    assert resolved.case.status is CaseStatus.APPROVED and resolved.case.closed_at == NOW
    assert (last.role, last.content) == (Role.CLINICIAN, DRAFT)
    assert clinician.pending_cases() == []


def test_modifying_sends_the_clinician_text(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")

    resolved = review(database).modify(case_id, "  Escríbeme si sigue el ardor.  ")

    last = thread_messages(database, "ana")[-1]
    assert resolved.case.status is CaseStatus.MODIFIED
    assert (last.role, last.content) == (Role.CLINICIAN, "Escríbeme si sigue el ardor.")


def test_a_resolved_case_cannot_be_answered_again(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    clinician = review(database)
    clinician.modify(case_id, "Primera respuesta.")

    with pytest.raises(CaseConflictError):
        clinician.modify(case_id, "Segunda respuesta.")
    assert len(thread_messages(database, "ana")) == 2


def test_an_expired_case_is_closed_and_cannot_be_answered(database: SqliteDatabase) -> None:
    case_id = person(database, "ana")
    clock = Clock(NOW + WINDOW)
    clinician = review(database, clock=clock)

    with pytest.raises(CaseConflictError):
        clinician.modify(case_id, "Tarde.")
    assert clinician.pending_cases() == []
    assert clinician.case(case_id).case.status is CaseStatus.EXPIRED


def test_whatsapp_cases_wait_for_phase_four(database: SqliteDatabase) -> None:
    case_id = person(database, "ana", Channel.WHATSAPP)

    with pytest.raises(CaseChannelNotSupportedError):
        review(database).modify(case_id, "Hola.")
    assert review(database).case(case_id).case.status is CaseStatus.PENDING


# --- El rol profesional nunca llega crudo al modelo -----------------------------------------


def test_a_clinician_message_reaches_the_model_as_an_assistant_with_its_prefix() -> None:
    message = ChatMessage(Role.CLINICIAN, "Consulta con tu EPS.", "t-ana", NOW)

    converted = for_model(message)

    assert (converted.role, converted.content) == (
        Role.ASSISTANT,
        f"{CLINICIAN_PREFIX} Consulta con tu EPS.",
    )
    assert for_model(ChatMessage(Role.USER, "hola")) == ChatMessage(Role.USER, "hola")


def test_no_context_sent_to_the_model_carries_the_clinician_role() -> None:
    analysis = AnalysisTurn(ThreadAction.CONTINUE, Domain.CARDIOVASCULAR, "", ())
    recent = (ChatMessage(Role.CLINICIAN, "Consulta con tu EPS.", "t-ana", NOW),)

    context = reply_context("PROMPT", analysis, TurnInput("gracias", recent), "EVIDENCIA")

    assert all(message.role is not Role.CLINICIAN for message in context)
