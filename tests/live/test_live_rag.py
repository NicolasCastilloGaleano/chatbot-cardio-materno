"""Pruebas en vivo del RAG y de la separación análisis/evidencia (HU-02, ADR 0008).

Requieren Ollama con los modelos y el índice construido (`run_build_kb_index.py`).
Ejecutar en el PC de pruebas: `pytest -m live -s` (con -s se ve el reporte).
"""

import json
from dataclasses import replace
from typing import Any

import pytest

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.application.agent_turn import ANALYSIS_SCHEMA, parse_analysis
from cardio_materno.application.alarm_policy import AlarmPolicy, render_system_prompt
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.application.turn_context import TurnInput, analysis_context
from cardio_materno.domain.alarms import AlertOrigin
from cardio_materno.domain.conversation import Domain
from tests.live.conftest import LIVE_DIR, make_retriever

pytestmark = pytest.mark.live

PROBE: list[dict[str, Any]] = json.loads(
    (LIVE_DIR / "retrieval_probe.json").read_text(encoding="utf-8")
)["cases"]
TOP_K = 3
MIN_PROBE_HITS = 13  # meta inicial: 13 de 16 casos con la categoría esperada en el top-3

# Preguntas educativas cuya evidencia menciona signos de alarma: el análisis NO debe reportar
# síntomas (la persona no dice tener nada). Verifica que no hay contaminación.
EDUCATIONAL_QUESTIONS = [
    "¿qué signos de alarma hay en el embarazo?",
    "¿cuáles son los síntomas de un infarto?",
    "¿qué señales de peligro puede tener un recién nacido?",
    "¿por qué es importante controlar la presión aunque no duela nada?",
]
# Reportes que el filtro 1 no capta y que el filtro 2 sí debe captar (incidentes del 2026-10-10).
SYMPTOM_REPORTS = [
    ("tengo 34 semanas y desde ayer el bebé está muy quietico", "RN-MI-06"),
    ("tengo 8 meses y mi barriga está como quieta, no hay pataditas desde la mañana", "RN-MI-06"),
]


def analyze(analyzer: OllamaLanguageModel, prompt: str, text: str) -> Any:
    """Ejecuta solo la llamada de análisis sobre un mensaje, sin hilo previo."""
    context = analysis_context(prompt, None, TurnInput(text))
    return parse_analysis(analyzer.complete_json(context, ANALYSIS_SCHEMA))


def test_retrieval_probe_finds_expected_category_in_top_k(evidence_policy: EvidencePolicy) -> None:
    retriever = make_retriever(replace(evidence_policy, min_similarity=0.0, top_k=TOP_K))
    hits = 0
    for case in PROBE:
        result = retriever.retrieve(EvidenceQuery(case["query"], (Domain(case["domain"]),)))
        categories = [item.entry.category for item in result.items]
        hit = any(category in case["expected_categories"] for category in categories)
        hits += hit
        scores = ", ".join(f"{item.score:.2f}" for item in result.items)
        print(f"{'✅' if hit else '❌'} {case['query']} → [{scores}] {categories[:1]}")
    print(f"Sonda: {hits}/{len(PROBE)} (meta ≥ {MIN_PROBE_HITS})")
    assert hits >= MIN_PROBE_HITS


@pytest.mark.parametrize("question", EDUCATIONAL_QUESTIONS)
def test_educational_question_reports_no_symptoms(
    analyzer: OllamaLanguageModel,
    analysis_prompt_template: str,
    alarm_policy: AlarmPolicy,
    question: str,
) -> None:
    analysis = analyze(
        analyzer, render_system_prompt(analysis_prompt_template, alarm_policy), question
    )

    assert analysis.reported_symptoms == ()


@pytest.mark.parametrize(("message", "rule_id"), SYMPTOM_REPORTS)
def test_colloquial_report_is_caught_by_filter_two(
    analyzer: OllamaLanguageModel,
    analysis_prompt_template: str,
    alarm_policy: AlarmPolicy,
    message: str,
    rule_id: str,
) -> None:
    assert alarm_policy.evaluate([message], AlertOrigin.USER) is None  # el filtro 1 no lo capta

    analysis = analyze(
        analyzer, render_system_prompt(analysis_prompt_template, alarm_policy), message
    )
    decision = alarm_policy.evaluate(["; ".join(analysis.reported_symptoms)], AlertOrigin.AGENT)

    print(f"{message} → {analysis.reported_symptoms}")
    assert decision is not None and rule_id in decision.rule_ids
