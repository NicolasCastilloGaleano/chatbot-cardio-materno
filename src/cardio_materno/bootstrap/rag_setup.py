"""Armado del RAG al arrancar: base, índice, política y modelo de embeddings (ADR 0008)."""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from cardio_materno.adapters.outbound.rag.hybrid_retriever import (
    HybridRetriever,
    check_entries_file,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import (
    KnowledgeBaseError,
    load_case_profiles,
    load_entries,
    load_policy,
)
from cardio_materno.adapters.outbound.rag.ollama_embedder import EmbedderSettings, OllamaEmbedder
from cardio_materno.adapters.outbound.rag.vector_index import load_index
from cardio_materno.application.conversation_service import UnavailableRetriever
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import KnowledgeRetriever
from cardio_materno.bootstrap.settings import PolicyOverrides, RagSettings
from cardio_materno.domain.knowledge import CaseProfile, KnowledgeEntry

MSG_RAG_DISABLED = "RAG desactivado (RAG_ENABLED=false): el asistente no dará información de salud."
MSG_RAG_UNAVAILABLE = (
    "⚠️  RAG no disponible: {error}\n"
    "    El asistente seguirá, pero sin información de salud (se abstendrá). "
    "Para construir el índice: python run_build_kb_index.py"
)
MSG_RAG_READY = (
    "Base de conocimiento: {count} registros · índice con '{model}' · umbral {threshold:.2f}"
)
MSG_CASES_READY = " · base v2 con {count} cuadros"


@dataclass(frozen=True)
class RagSetup:
    """Resultado de preparar el RAG.

    Attributes:
        retriever: Buscador de evidencia (nulo si el RAG no está disponible).
        policy: Política de evidencia.
        status_message: Mensaje informativo para mostrar al arrancar.
        case_profiles: Cuadros de la base v2 por motivo (vacío con la base v1).
    """

    retriever: KnowledgeRetriever
    policy: EvidencePolicy
    status_message: str
    case_profiles: dict[str, CaseProfile] = field(default_factory=dict)


def build_embedder(settings: RagSettings, base_url: str) -> OllamaEmbedder:
    """Crea el adaptador del modelo de embeddings."""
    return OllamaEmbedder(
        EmbedderSettings(
            base_url=base_url,
            model=settings.embed_model,
            timeout_seconds=settings.embed_timeout_seconds,
            batch_size=settings.embed_batch_size,
            keep_alive=settings.keep_alive,
            num_gpu=settings.embed_num_gpu,
        )
    )


def load_effective_policy(settings: RagSettings) -> EvidencePolicy:
    """Política de evidencia del archivo, con los umbrales que se fijen en .env encima.

    Raises:
        KnowledgeBaseError: Si el archivo de política no existe o es inválido.
    """
    return apply_policy_overrides(load_policy(settings.policy_file), settings.policy_overrides)


def apply_policy_overrides(policy: EvidencePolicy, overrides: PolicyOverrides) -> EvidencePolicy:
    """Reemplaza en la política los umbrales que vienen de .env (los vacíos no cambian)."""

    def pick[T](value: T | None, current: T) -> T:
        return current if value is None else value

    return replace(
        policy,
        min_similarity=pick(overrides.min_similarity, policy.min_similarity),
        top_k=pick(overrides.top_k, policy.top_k),
        candidate_k=pick(overrides.candidate_k, policy.candidate_k),
        min_support=pick(overrides.min_support, policy.min_support),
        max_free_sentences=pick(overrides.max_free_sentences, policy.max_free_sentences),
        max_free_words=pick(overrides.max_free_words, policy.max_free_words),
    )


def setup_rag(settings: RagSettings, base_url: str) -> RagSetup:
    """Prepara el buscador; si algo falta, devuelve un buscador nulo con un aviso claro.

    Raises:
        KnowledgeBaseError: Si la política de evidencia no existe o es inválida.
    """
    policy = load_effective_policy(settings)
    if not settings.enabled:
        return RagSetup(UnavailableRetriever(), policy, MSG_RAG_DISABLED)
    try:
        entries = load_entries(settings.entries_file)
        profiles = load_profiles_for(entries, settings.cases_file)
        retriever = _build_retriever(entries, settings, base_url, policy)
    except (KnowledgeBaseError, LanguageModelError) as error:
        return RagSetup(UnavailableRetriever(), policy, MSG_RAG_UNAVAILABLE.format(error=error))
    ready = MSG_RAG_READY.format(
        count=len(entries), model=settings.embed_model, threshold=policy.min_similarity
    )
    cases = MSG_CASES_READY.format(count=len(profiles)) if profiles else ""
    return RagSetup(retriever, policy, ready + cases, profiles)


def load_profiles_for(
    entries: Sequence[KnowledgeEntry], cases_file: Path
) -> dict[str, CaseProfile]:
    """Cuadros de la base v2, solo si la base los usa (vacío con la base v1).

    Args:
        entries: Registros ya cargados de la base.
        cases_file: Archivo de cuadros (`cuadros.jsonl`).

    Returns:
        Los cuadros de los motivos que aparecen en la base, por motivo.

    Raises:
        KnowledgeBaseError: Si la base tiene cuadros y falta el archivo de cuadros, o si
            algún cuadro de la base no está en él.
    """
    motives = {entry.motive for entry in entries if entry.motive}
    if not motives:
        return {}
    profiles = {profile.motive: profile for profile in load_case_profiles(cases_file)}
    missing = sorted(motives - set(profiles))
    if missing:
        raise KnowledgeBaseError(f"Faltan cuadros en {cases_file.name}: {missing[:5]}")
    return {motive: profiles[motive] for motive in motives}


def _build_retriever(
    entries: Sequence[KnowledgeEntry], settings: RagSettings, base_url: str, policy: EvidencePolicy
) -> HybridRetriever:
    """Carga el índice, verifica y precalienta el modelo y crea el buscador."""
    index = load_index(settings.index_dir)
    check_entries_file(index, settings.entries_file)
    embedder = build_embedder(settings, base_url)
    embedder.verify_ready()
    embedder.warm_up()
    return HybridRetriever(entries, index, embedder, policy)
