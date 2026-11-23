"""Pruebas del escalamiento al profesional en el servicio (HU-16, ADR 0022, fase 1)."""

from dataclasses import replace
from typing import Any

from cardio_materno.application.conversation_service import ConversationService, TurnResult
from cardio_materno.application.escalation import (
    ALREADY_WAITING_TEXT,
    WAITING_TEXT,
    EscalationMode,
    escalation_gap,
    with_waiting_text,
)
from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    CLOSING_TEXT,
    NO_INFORMATION_TEXT,
)
from cardio_materno.domain.escalation import CaseStatus
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import ReplyTrace
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    FakeRetriever,
    InMemoryCaseRepository,
    InMemoryThreadRepository,
    ScriptedAgent,
    make_alarm_policy,
    make_service,
)
from tests.unit.test_inquiry_observation import reporting

ACTIVE = {"escalation": EscalationMode.ACTIVE}
NOTHING = RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.42)


def escalating_service(
    cases: InMemoryCaseRepository | None, retrieval: RetrievalResult, turns: int, config: Any
) -> ConversationService:
    """Servicio con los dobles de siempre y el repositorio de casos de la persona."""
    agent = ScriptedAgent(*(reporting("r", reported_symptoms=["ardor en el estómago"]),) * turns)
    service = make_service(agent, InMemoryThreadRepository(), config, FakeRetriever(retrieval))
    ports = replace(service._ports, cases=cases)  # noqa: SLF001
    return ConversationService(ports, service._config)  # noqa: SLF001


def send(
    *texts: str, retrieval: RetrievalResult = NOTHING, **config: Any
) -> tuple[list[TurnResult], InMemoryCaseRepository]:
    cases = InMemoryCaseRepository()
    service = escalating_service(cases, retrieval, len(texts), ACTIVE | config)
    return [service.send(text) for text in texts], cases


def test_a_turn_without_evidence_gets_the_waiting_text_and_opens_a_case() -> None:
    (result,), cases = send("me arde el estómago")

    (case,) = cases.cases.values()
    assert result.reply == WAITING_TEXT
    assert result.escalated_case_id == case.id
    assert (case.status, case.notified, case.thread_id) == (CaseStatus.PENDING, True, "hilo-1")
    assert case.snapshot.symptoms == ("ardor en el estómago",)
    assert case.snapshot.best_score == 0.42


def test_a_second_gap_reminds_the_wait_and_uses_the_same_case() -> None:
    (first, second), cases = send("me arde el estómago", "sigue ardiendo")

    (case,) = cases.cases.values()
    assert (first.reply, second.reply) == (WAITING_TEXT, ALREADY_WAITING_TEXT)
    assert first.escalated_case_id == second.escalated_case_id == case.id
    assert case.gap_count == 2


def test_observing_keeps_the_abstention_and_records_the_case() -> None:
    (result,), cases = send("me arde el estómago", escalation=EscalationMode.OBSERVE)

    (case,) = cases.cases.values()
    assert result.reply == ABSTENTION_TEXT and not case.notified


def test_turned_off_or_without_cases_nothing_escalates() -> None:
    (off,), off_cases = send("me arde el estómago", escalation=EscalationMode.OFF)
    service = escalating_service(None, NOTHING, 1, ACTIVE)

    assert off.reply == ABSTENTION_TEXT and not off_cases.cases
    assert service.send("me arde el estómago").escalated_case_id is None


def test_an_alarm_never_escalates() -> None:
    (result,), cases = send("tengo la presión alta", alarm_policy=make_alarm_policy())

    assert PRIORITY_MESSAGE in result.reply and WAITING_TEXT not in result.reply
    assert not cases.cases and result.escalated_case_id is None


def test_an_unavailable_search_is_not_a_gap() -> None:
    unavailable = RetrievalResult(RetrievalStatus.UNAVAILABLE)

    (result,), cases = send("me arde el estómago", retrieval=unavailable)

    assert WAITING_TEXT not in result.reply and not cases.cases


def test_a_verified_answer_does_not_escalate() -> None:
    assert escalation_gap("DASH es un patrón alimentario.", ReplyTrace(), alarmed=False) is None
    assert escalation_gap(ABSTENTION_TEXT, ReplyTrace(), alarmed=True) is None
    assert escalation_gap(ABSTENTION_TEXT, ReplyTrace(), alarmed=False) is not None


def test_the_waiting_text_replaces_only_the_abstention_or_the_closing() -> None:
    reminder = "Recuerda lo que te dije sobre la presión."

    assert with_waiting_text(f"{reminder} {ABSTENTION_TEXT}", WAITING_TEXT) == (
        f"{reminder} {WAITING_TEXT}"
    )
    assert with_waiting_text(NO_INFORMATION_TEXT, WAITING_TEXT) == WAITING_TEXT
    assert with_waiting_text(CLOSING_TEXT, WAITING_TEXT) == WAITING_TEXT
    assert with_waiting_text("Otra respuesta.", WAITING_TEXT) == "Otra respuesta."
