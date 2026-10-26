"""Pruebas de las reglas deterministas de alcance (HU-07, ADR 0009)."""

import pytest

from cardio_materno.application.agent_turn import AnalysisTurn, Scope, ThreadAction
from cardio_materno.application.scope import OUT_OF_SCOPE_MESSAGE, effective_scope
from cardio_materno.domain.conversation import ChatMessage, Domain, Role


def analysis(scope: Scope, domain: Domain, symptoms: tuple[str, ...] = ()) -> AnalysisTurn:
    return AnalysisTurn(ThreadAction.NEW, domain, "resumen", symptoms, scope, "motivo")


def test_reported_symptoms_in_our_domains_are_always_in_scope() -> None:
    result = effective_scope(analysis(Scope.OUT_OF_SCOPE, Domain.MATERNAL_CHILD, ("acidez",)))

    assert result is Scope.IN_SCOPE


@pytest.mark.parametrize("scope", list(Scope))
def test_without_symptoms_the_analysis_decision_is_kept(scope: Scope) -> None:
    assert effective_scope(analysis(scope, Domain.CARDIOVASCULAR)) is scope


def test_symptoms_of_uncertain_domain_are_never_discarded() -> None:
    symptom = ("dolor muy fuerte en el brazo",)

    result = effective_scope(analysis(Scope.OUT_OF_SCOPE, Domain.NONE, symptom))

    assert result is Scope.IN_SCOPE


def test_marked_sign_code_keeps_the_message_in_scope() -> None:
    analysis = AnalysisTurn(
        ThreadAction.NEW,
        Domain.NONE,
        "s",
        reported_signs=("DESMAYO",),
        scope=Scope.OUT_OF_SCOPE,
    )

    assert effective_scope(analysis) is Scope.IN_SCOPE


ASKED = (
    ChatMessage(Role.USER, "mi bebé tiene fiebre"),
    ChatMessage(Role.ASSISTANT, "¿Desde cuándo tiene fiebre? Mídele la temperatura."),
)


def out_of_scope(thread_action: ThreadAction) -> AnalysisTurn:
    return AnalysisTurn(thread_action, Domain.NONE, "s", (), Scope.OUT_OF_SCOPE, "sin salud")


def test_answer_to_a_pending_question_is_never_discarded() -> None:
    assert effective_scope(out_of_scope(ThreadAction.CONTINUE), ASKED) is Scope.IN_SCOPE


def test_new_topic_with_a_pending_question_stays_out_of_scope() -> None:
    assert effective_scope(out_of_scope(ThreadAction.NEW), ASKED) is Scope.OUT_OF_SCOPE


def test_without_a_pending_question_the_analysis_decision_is_kept() -> None:
    no_question = (ChatMessage(Role.ASSISTANT, "Mídele la temperatura."),)

    result = effective_scope(out_of_scope(ThreadAction.CONTINUE), no_question)

    assert result is Scope.OUT_OF_SCOPE


def test_only_the_last_assistant_message_counts_as_pending_question() -> None:
    answered = (*ASKED, ChatMessage(Role.USER, "desde ayer"), ChatMessage(Role.ASSISTANT, "Ok."))

    result = effective_scope(out_of_scope(ThreadAction.CONTINUE), answered)

    assert result is Scope.OUT_OF_SCOPE


def test_without_thread_there_is_no_pending_question() -> None:
    assert effective_scope(out_of_scope(ThreadAction.CONTINUE)) is Scope.OUT_OF_SCOPE


def test_out_of_scope_message_invites_the_person_to_continue() -> None:
    assert OUT_OF_SCOPE_MESSAGE.rstrip().endswith("?")
