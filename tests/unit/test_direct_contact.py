"""Pruebas del contacto directo con el profesional (HU-16, ADR 0022, fase 3)."""

from datetime import UTC, datetime

from cardio_materno.application.conversation_service import ConversationService
from cardio_materno.application.escalation import WAITING_TEXT
from cardio_materno.domain.conversation import Role
from cardio_materno.domain.escalation import CaseAction, CaseStatus, ClinicalCase, apply_action
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    InMemoryCaseRepository,
    make_alarm_policy,
)
from tests.unit.test_escalation import ACTIVE, NOTHING, escalating_service

STARTED = datetime(2026, 10, 10, 12, 0, 30, tzinfo=UTC)


def in_contact(
    turns: int = 1, **config: object
) -> tuple[ConversationService, InMemoryCaseRepository]:
    """Servicio con un caso que el profesional ya pasó a contacto directo."""
    cases = InMemoryCaseRepository()
    service = escalating_service(cases, NOTHING, turns, ACTIVE | config)
    assert service.send("me arde el estómago").reply == WAITING_TEXT
    (case,) = cases.cases.values()
    cases.cases[case.id] = apply_action(case, CaseAction.START_CONTACT, STARTED)
    return service, cases


def agent_calls(service: ConversationService) -> list[object]:
    """Llamadas que recibió el modelo de análisis (doble guionizado)."""
    return list(service._ports.analyzer.calls)  # type: ignore[attr-defined]  # noqa: SLF001


def only_case(cases: InMemoryCaseRepository) -> ClinicalCase:
    (case,) = cases.cases.values()
    return case


def test_in_contact_the_message_goes_to_the_clinician_without_any_model_call() -> None:
    service, cases = in_contact()
    calls_before = len(agent_calls(service))

    result = service.send("gracias, sigo con ardor")

    assert (result.reply, result.relayed, result.alerts) == ("", True, ())
    assert len(agent_calls(service)) == calls_before
    last = service._ports.repository.all_messages(only_case(cases).thread_id)[-1]  # noqa: SLF001
    assert (last.role, last.content) == (Role.USER, "gracias, sigo con ardor")


def test_an_alarm_during_contact_still_gets_its_fixed_notice() -> None:
    service, cases = in_contact(alarm_policy=make_alarm_policy())

    result = service.send("tengo la presión alta")

    assert PRIORITY_MESSAGE in result.reply and result.relayed and result.alerts
    assert only_case(cases).status is CaseStatus.IN_CONTACT


def test_each_message_renews_the_case_window() -> None:
    service, cases = in_contact()
    before = only_case(cases).expires_at

    service.send("hola, ¿sigue ahí?")

    assert only_case(cases).expires_at > before


def test_after_the_contact_closes_the_assistant_answers_again() -> None:
    service, cases = in_contact(turns=2)
    case = only_case(cases)
    cases.cases[case.id] = apply_action(case, CaseAction.CLOSE, STARTED)

    result = service.send("otra pregunta")

    assert not result.relayed
