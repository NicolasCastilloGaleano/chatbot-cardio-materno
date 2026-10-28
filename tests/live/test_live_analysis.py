"""Pruebas en vivo del análisis v3: sin datos inventados ni arrastrados y consulta de búsqueda.

Reproducen los incidentes del guion del 2026-10-11 y comparan la búsqueda con la consulta
reformulada (`search_query`) frente a la consulta anterior (mensaje + resumen + síntomas).
Ejecutar en el PC de pruebas: `pytest -m live -s`.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.application.agent_turn import (
    AnalysisTurn,
    ThreadAction,
)
from cardio_materno.application.alarm_policy import AlarmPolicy, render_system_prompt
from cardio_materno.application.evidence import EvidencePolicy, build_evidence_query
from cardio_materno.application.grounded_reply import ABSTENTION_TEXT
from cardio_materno.application.turn_context import TurnInput, analysis_context
from cardio_materno.domain.conversation import ChatMessage, Domain, Role, open_thread
from cardio_materno.domain.grounding import unstated_details
from cardio_materno.domain.knowledge import EvidenceItem
from tests.live.conftest import agent_rule_ids, complete_analysis, make_retriever

pytestmark = pytest.mark.live

HEARTBURN_SUMMARY = "La persona tiene acidez en el embarazo."
HEARTBURN_TURN = (
    ChatMessage(Role.USER, "tengo acidez en el embarazo"),
    ChatMessage(Role.ASSISTANT, "Describe si el ardor sube hacia el pecho y qué lo desencadena."),
)
PRESSURE = "Presión arterial y riesgo cardiovascular"
STROKE = "Eventos cerebrovasculares"
THROMBOSIS = "Circulación periférica, trombosis y enfermedad venosa"
PREGNANCY = "Materno — embarazo, dolor, sangrado y bienestar fetal"
# Mensajes coloquiales o mixtos y la categoría que debería recuperar la búsqueda.
SEARCH_CASES = [
    ("¿quién ganó el partido? ah, y tengo la presión alta", PRESSURE),
    ("se me torció la boca y no puedo mover un brazo", STROKE),
    ("tengo una pierna hinchada, roja y caliente", THROMBOSIS),
    (
        "estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas, ¿es normal?",
        PREGNANCY,
    ),
]


@pytest.fixture(scope="module")
def prompt(analysis_prompt_template: str, alarm_policy: AlarmPolicy) -> str:
    return render_system_prompt(analysis_prompt_template, alarm_policy)


def analyze_in_heartburn_thread(
    analyzer: OllamaLanguageModel, policy: AlarmPolicy, prompt: str, text: str
) -> AnalysisTurn:
    """Análisis real de un mensaje dentro de un hilo sobre acidez en el embarazo (sin semanas)."""
    thread = open_thread("hilo-vivo", Domain.MATERNAL_CHILD, HEARTBURN_SUMMARY, datetime.now(UTC))
    context = analysis_context(prompt, thread, TurnInput(text, HEARTBURN_TURN))
    return complete_analysis(analyzer, policy, context)


def test_follow_up_does_not_invent_pregnancy_weeks(
    analyzer: OllamaLanguageModel, prompt: str, alarm_policy: AlarmPolicy
) -> None:
    analysis = analyze_in_heartburn_thread(
        analyzer, alarm_policy, prompt, "¿y qué más puedo comer?"
    )

    print(f"seguimiento → {analysis.reported_symptoms} · {analysis.summary}")
    said = ["tengo acidez en el embarazo", "¿y qué más puedo comer?"]
    assert unstated_details([*analysis.reported_symptoms, analysis.summary], said) == ()


def test_new_topic_does_not_carry_symptoms_from_the_previous_thread(
    analyzer: OllamaLanguageModel, prompt: str, alarm_policy: AlarmPolicy
) -> None:
    analysis = analyze_in_heartburn_thread(analyzer, alarm_policy, prompt, "mi bebé tiene fiebre")

    print(f"tema nuevo → {analysis.thread_action} · {analysis.reported_symptoms}")
    assert "RN-MI-07" not in agent_rule_ids(alarm_policy, analysis)
    if analysis.thread_action is ThreadAction.NEW:
        assert not any("acidez" in symptom.lower() for symptom in analysis.reported_symptoms)


def test_search_query_finds_the_expected_category_at_least_as_often(
    analyzer: OllamaLanguageModel,
    prompt: str,
    evidence_policy: EvidencePolicy,
    alarm_policy: AlarmPolicy,
) -> None:
    retriever = make_retriever(evidence_policy)
    old_hits = new_hits = 0
    for message, expected in SEARCH_CASES:
        context = analysis_context(prompt, None, TurnInput(message))
        analysis = complete_analysis(analyzer, alarm_policy, context)
        old_query = build_evidence_query(without_search_query(analysis), message)
        old_ok = finds(retriever.retrieve(old_query).items, expected)
        new_ok = finds(retriever.retrieve(build_evidence_query(analysis, message)).items, expected)
        old_hits, new_hits = old_hits + old_ok, new_hits + new_ok
        print(f"{message}\n    search_query={analysis.search_query!r} · antes {old_ok} → {new_ok}")
    print(f"Con el umbral real: antes {old_hits}/{len(SEARCH_CASES)} → ahora {new_hits}")
    assert new_hits >= old_hits


def without_search_query(analysis: AnalysisTurn) -> AnalysisTurn:
    """El mismo análisis sin consulta reformulada (comportamiento anterior)."""
    return AnalysisTurn(
        analysis.thread_action, analysis.domain, analysis.summary, analysis.reported_symptoms
    )


def finds(items: Sequence[EvidenceItem], expected: str) -> bool:
    """True si la categoría esperada está entre la evidencia que superó el umbral."""
    return any(item.entry.category == expected for item in items)


def test_details_asked_by_the_assistant_continue_a_thread_without_domain(
    analyzer: OllamaLanguageModel, prompt: str, alarm_policy: AlarmPolicy
) -> None:
    """Guion de la HU-11 (2026-10-27): la respuesta a la abstención abría un hilo nuevo."""
    thread = open_thread(
        "hilo-vivo", Domain.NONE, "La persona tiene un ardor raro.", datetime.now(UTC)
    )
    recent = (
        ChatMessage(Role.USER, "tengo un ardor raro"),
        ChatMessage(Role.ASSISTANT, ABSTENTION_TEXT),
    )
    turn = TurnInput("es en el pecho, después de comer", recent)

    analysis = complete_analysis(analyzer, alarm_policy, analysis_context(prompt, thread, turn))

    print(f"detalles pedidos → {analysis.thread_action} · {analysis.domain}")
    assert analysis.thread_action is ThreadAction.CONTINUE
