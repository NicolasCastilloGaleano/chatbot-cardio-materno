"""Arma la comparación v8/v9 con el modelo, el catálogo y el índice reales (ADR 0023).

Solo funciona donde están Ollama, los modelos de `.env` y, para la recuperación, el índice
construido (`run_build_kb_index.py`). Si falta algo, lo dice y no compara nada: nunca
sustituye un recurso real por uno simulado.
"""

from collections.abc import Mapping
from pathlib import Path

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    load_care_access_catalog,
)
from cardio_materno.adapters.outbound.llm.ollama_language_model import (
    OllamaLanguageModel,
    OllamaSettings,
)
from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.knowledge_files import load_entries
from cardio_materno.adapters.outbound.rag.vector_index import load_index
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import ENV_FILE, PROJECT_ROOT, STARTUP_ERRORS, analysis_prompt
from cardio_materno.bootstrap.rag_setup import build_embedder, load_effective_policy
from cardio_materno.bootstrap.settings import (
    ANALYSIS_MODEL_VARIABLE,
    load_conversation_settings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
)
from scripts.compare_analysis_prompts import V8, V9, Bench, Search, Variant, digest


class LiveSetupError(RuntimeError):
    """El equipo no tiene lo necesario para comparar con el modelo real."""


def build_live_bench(
    env: Mapping[str, str], with_retrieval: bool
) -> tuple[Bench, tuple[Variant, Variant], list[str]]:
    """Conecta el modelo de análisis y, si se pide, el buscador real.

    Args:
        env: Variables de entorno (se completa con `.env`).
        with_retrieval: True para medir también la recuperación con el índice real.

    Returns:
        Lo que es común a las dos variantes, las variantes y el encabezado del informe.

    Raises:
        LiveSetupError: Si falta Ollama, un modelo, el catálogo o el índice.
    """
    load_env_file(ENV_FILE)
    try:
        conversation = load_conversation_settings(env, PROJECT_ROOT)
        policy = load_alarm_policy(conversation.alarm_rules_file)
        catalog = load_care_access_catalog(conversation.care_access_file)
        stage = load_stage_settings(env, ANALYSIS_MODEL_VARIABLE)
        analyzer = OllamaLanguageModel(stage)
        analyzer.verify_ready()
        analyzer.warm_up()
        search, index_line = live_search(env) if with_retrieval else (None, "no medida")
    except (*STARTUP_ERRORS, OSError) as error:
        raise LiveSetupError(str(error)) from error
    variants = (
        Variant(V8, analysis_prompt(policy, None)),
        Variant(V9, analysis_prompt(policy, catalog), catalog.codes),
    )
    return Bench(analyzer, policy, search), variants, header(stage, variants, index_line)


def live_search(env: Mapping[str, str]) -> tuple[Search, str]:
    """Buscador real con la política de evidencia de `.env` y la huella de lo que indexa."""
    settings = load_rag_settings(env, PROJECT_ROOT)
    embedder = build_embedder(settings, load_ollama_settings(env).base_url)
    embedder.verify_ready()
    retriever = HybridRetriever(
        load_entries(settings.entries_file),
        load_index(settings.index_dir),
        embedder,
        load_effective_policy(settings),
    )
    return retriever.retrieve, f"{settings.embed_model} · {file_digest(settings.entries_file)}"


def file_digest(path: Path) -> str:
    """Huella corta del contenido de un archivo."""
    return digest(path.read_text(encoding="utf-8"))


def header(stage: OllamaSettings, variants: tuple[Variant, Variant], index_line: str) -> list[str]:
    """Líneas del informe que dicen qué se comparó y con qué configuración."""
    v8, v9 = variants
    return [
        f"- Modelo de análisis: `{stage.model}` · temperatura {stage.temperature} · "
        f"contexto {stage.num_ctx} tokens",
        f"- Prompt v8: {len(v8.prompt)} caracteres (`{digest(v8.prompt)}`)",
        f"- Prompt v9: {len(v9.prompt)} caracteres (`{digest(v9.prompt)}`)",
        f"- Recuperación (modelo de embeddings · corpus): {index_line}",
    ]
