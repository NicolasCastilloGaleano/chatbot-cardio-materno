"""Pruebas de las reglas deterministas de alcance (HU-07, ADR 0009)."""

import pytest

from cardio_materno.application.agent_turn import AnalysisTurn, Scope, ThreadAction
from cardio_materno.application.scope import effective_scope
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


# --- Respuesta a una pregunta pendiente del asistente (MIG-01) ----------------------------

PENDING = (
    ChatMessage(Role.USER, "mi bebé tiene fiebre"),
    ChatMessage(Role.ASSISTANT, "Gracias por contarme. ¿Desde cuándo tiene fiebre?"),
)
NO_PENDING = (
    ChatMessage(Role.USER, "mi bebé tiene fiebre"),
    ChatMessage(Role.ASSISTANT, "Ofrécele líquidos con frecuencia."),
)


def follow_up(scope: Scope, action: ThreadAction = ThreadAction.CONTINUE) -> AnalysisTurn:
    return AnalysisTurn(action, Domain.NONE, "resumen", (), scope, "sin síntomas")


def test_answer_to_a_pending_question_is_never_out_of_scope() -> None:
    assert effective_scope(follow_up(Scope.OUT_OF_SCOPE), PENDING) is Scope.IN_SCOPE


def test_new_topic_with_a_pending_question_keeps_the_analysis_decision() -> None:
    analysis = follow_up(Scope.OUT_OF_SCOPE, ThreadAction.NEW)

    assert effective_scope(analysis, PENDING) is Scope.OUT_OF_SCOPE


def test_without_a_pending_question_the_analysis_decision_is_kept() -> None:
    assert effective_scope(follow_up(Scope.OUT_OF_SCOPE), NO_PENDING) is Scope.OUT_OF_SCOPE
    assert effective_scope(follow_up(Scope.OUT_OF_SCOPE)) is Scope.OUT_OF_SCOPE


def test_thanks_after_a_question_stays_conversational() -> None:
    assert effective_scope(follow_up(Scope.CONVERSATIONAL), PENDING) is Scope.CONVERSATIONAL
