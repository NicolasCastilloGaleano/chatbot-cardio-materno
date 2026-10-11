"""Pruebas en vivo del control de alcance de la llamada de análisis (HU-07, ADR 0009).

Ejecutar en el PC de pruebas: `pytest -m live -s`.
"""

from datetime import UTC, datetime

import pytest

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.application.agent_turn import (
    ANALYSIS_SCHEMA,
    AnalysisTurn,
    Scope,
    parse_analysis,
)
from cardio_materno.application.alarm_policy import AlarmPolicy, render_system_prompt
from cardio_materno.application.scope import effective_scope
from cardio_materno.application.turn_context import TurnInput, analysis_context
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread

pytestmark = pytest.mark.live

IN_SCOPE_WITH_FOREIGN_CONTEXT = [
    "estaba cocinando unos frijoles y empecé a sentir acidez en el estómago, "
    "tengo 34 semanas de embarazo, ¿es normal?",
    "estaba viendo el partido y el corazón me empezó a latir muy rápido",
    "¿quién ganó el partido? ah, y tengo la presión alta",
    "¿es malo comer mucha sal?",
]
OUT_OF_SCOPE = [
    "¿qué opinas del fútbol?",
    "ayúdame con la tarea de matemáticas",
    "¿por quién debería votar en las elecciones?",
]
CONVERSATIONAL = ["hola", "muchas gracias"]


def analyze(
    analyzer: OllamaLanguageModel, prompt: str, turn: TurnInput, thread_summary: str = ""
) -> AnalysisTurn:
    """Llamada de análisis real; con `thread_summary` simula un hilo activo."""
    now = datetime.now(UTC)
    thread = (
        open_thread("hilo-vivo", Domain.MATERNAL_CHILD, thread_summary, now)
        if thread_summary
        else None
    )
    return parse_analysis(
        analyzer.complete_json(analysis_context(prompt, thread, turn), ANALYSIS_SCHEMA)
    )


@pytest.fixture(scope="module")
def prompt(analysis_prompt_template: str, alarm_policy: AlarmPolicy) -> str:
    return render_system_prompt(analysis_prompt_template, alarm_policy)


@pytest.mark.parametrize("message", IN_SCOPE_WITH_FOREIGN_CONTEXT)
def test_foreign_context_does_not_take_message_out_of_scope(
    analyzer: OllamaLanguageModel, prompt: str, message: str
) -> None:
    analysis = analyze(analyzer, prompt, TurnInput(message))

    print(f"{message} → {analysis.scope} ({analysis.scope_reason})")
    assert effective_scope(analysis) is Scope.IN_SCOPE


@pytest.mark.parametrize("message", OUT_OF_SCOPE)
def test_completely_unrelated_message_is_out_of_scope(
    analyzer: OllamaLanguageModel, prompt: str, message: str
) -> None:
    analysis = analyze(analyzer, prompt, TurnInput(message))

    print(f"{message} → {analysis.scope} ({analysis.scope_reason})")
    assert effective_scope(analysis) is Scope.OUT_OF_SCOPE


@pytest.mark.parametrize("message", CONVERSATIONAL)
def test_greetings_are_conversational(
    analyzer: OllamaLanguageModel, prompt: str, message: str
) -> None:
    assert analyze(analyzer, prompt, TurnInput(message)).scope is Scope.CONVERSATIONAL


def test_follow_up_inside_a_thread_is_in_scope(analyzer: OllamaLanguageModel, prompt: str) -> None:
    recent = (
        ChatMessage(Role.USER, "mi bebé de 8 meses tiene fiebre"),
        ChatMessage(
            Role.ASSISTANT, "¿Desde cuándo tiene fiebre y cuánto le ha marcado el termómetro?"
        ),
    )
    turn = TurnInput("sí, desde ayer", recent)

    analysis = analyze(analyzer, prompt, turn, thread_summary="Bebé de 8 meses con fiebre.")

    print(f"seguimiento → {analysis.scope} ({analysis.scope_reason})")
    assert effective_scope(analysis) is Scope.IN_SCOPE
