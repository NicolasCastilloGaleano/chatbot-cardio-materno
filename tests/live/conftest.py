"""Configuración de las pruebas en vivo: necesitan Ollama, los modelos y el índice construido.

Se ejecutan solo en el PC de pruebas con `pytest -m live`. Fuera de ese modo se omiten.
"""

import os
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.knowledge_files import load_entries, load_policy
from cardio_materno.adapters.outbound.rag.vector_index import load_index
from cardio_materno.application.agent_turn import AnalysisTurn, analysis_schema, parse_analysis
from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import ANALYSIS_PROMPT_FILE, ENV_FILE, PROJECT_ROOT
from cardio_materno.bootstrap.rag_setup import build_embedder
from cardio_materno.bootstrap.settings import (
    ANALYSIS_MODEL_VARIABLE,
    load_conversation_settings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
)
from cardio_materno.domain.alarms import AlertOrigin
from cardio_materno.domain.conversation import ChatMessage

LIVE_DIR = Path(__file__).parent


@pytest.fixture(scope="session", autouse=True)
def live_environment() -> None:
    """Carga `.env` del proyecto antes de las pruebas en vivo."""
    load_env_file(ENV_FILE)


@pytest.fixture(scope="session")
def alarm_policy() -> AlarmPolicy:
    """Catálogo real de alarmas."""
    return load_alarm_policy(load_conversation_settings(os.environ, PROJECT_ROOT).alarm_rules_file)


@pytest.fixture(scope="session")
def analyzer() -> OllamaLanguageModel:
    """Modelo real de la llamada de análisis."""
    model = OllamaLanguageModel(load_stage_settings(os.environ, ANALYSIS_MODEL_VARIABLE))
    model.verify_ready()
    return model


@pytest.fixture(scope="session")
def analysis_prompt_template() -> str:
    """Prompt de análisis sin renderizar."""
    return ANALYSIS_PROMPT_FILE.read_text(encoding="utf-8").strip()


def make_retriever(policy: EvidencePolicy) -> HybridRetriever:
    """Buscador real (índice construido + modelo de embeddings) con la política dada."""
    settings = load_rag_settings(os.environ, PROJECT_ROOT)
    embedder = build_embedder(settings, load_ollama_settings(os.environ).base_url)
    embedder.verify_ready()
    return HybridRetriever(
        load_entries(settings.entries_file), load_index(settings.index_dir), embedder, policy
    )


@pytest.fixture(scope="session")
def evidence_policy() -> EvidencePolicy:
    """Política de evidencia real."""
    return load_policy(load_rag_settings(os.environ, PROJECT_ROOT).policy_file)


def complete_analysis(
    analyzer: OllamaLanguageModel, policy: AlarmPolicy, messages: list[ChatMessage]
) -> AnalysisTurn:
    """Llamada de análisis real con el esquema de códigos de signos del catálogo (ADR 0012)."""
    data = analyzer.complete_json(messages, analysis_schema(policy.codes))
    return parse_analysis(data, policy.codes)


def agent_rule_ids(policy: AlarmPolicy, analysis: AnalysisTurn) -> set[str]:
    """Reglas que activa el filtro 2: síntomas en texto o códigos de signos marcados."""
    by_text = policy.evaluate(analysis.reported_symptoms, AlertOrigin.AGENT)
    by_code = policy.evaluate_codes(analysis.reported_signs)
    return {rule_id for d in (by_text, by_code) if d is not None for rule_id in d.rule_ids}
