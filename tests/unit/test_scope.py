"""Pruebas de las reglas deterministas de alcance (HU-07, ADR 0009)."""

import pytest

from cardio_materno.application.agent_turn import AnalysisTurn, Scope, ThreadAction
from cardio_materno.application.scope import effective_scope
from cardio_materno.domain.conversation import Domain


def analysis(scope: Scope, domain: Domain, symptoms: tuple[str, ...] = ()) -> AnalysisTurn:
    return AnalysisTurn(ThreadAction.NEW, domain, "resumen", symptoms, scope, "motivo")


def test_reported_symptoms_in_our_domains_are_always_in_scope() -> None:
    result = effective_scope(analysis(Scope.OUT_OF_SCOPE, Domain.MATERNAL_CHILD, ("acidez",)))

    assert result is Scope.IN_SCOPE


@pytest.mark.parametrize("scope", list(Scope))
def test_without_symptoms_the_analysis_decision_is_kept(scope: Scope) -> None:
    assert effective_scope(analysis(scope, Domain.CARDIOVASCULAR)) is scope


def test_symptoms_with_domain_none_do_not_force_scope() -> None:
    result = effective_scope(analysis(Scope.OUT_OF_SCOPE, Domain.NONE, ("dolor de muela",)))

    assert result is Scope.OUT_OF_SCOPE


def test_marked_sign_code_keeps_the_message_in_scope() -> None:
    analysis = AnalysisTurn(
        ThreadAction.NEW,
        Domain.NONE,
        "s",
        reported_signs=("DESMAYO",),
        scope=Scope.OUT_OF_SCOPE,
    )

    assert effective_scope(analysis) is Scope.IN_SCOPE
