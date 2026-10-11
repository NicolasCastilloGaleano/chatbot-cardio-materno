"""Armado del RAG al arrancar: base, índice, política y modelo de embeddings (ADR 0008)."""

from dataclasses import dataclass

from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.knowledge_files import (
    KnowledgeBaseError,
    load_entries,
    load_policy,
)
from cardio_materno.adapters.outbound.rag.ollama_embedder import EmbedderSettings, OllamaEmbedder
from cardio_materno.adapters.outbound.rag.vector_index import load_index
from cardio_materno.application.conversation_service import UnavailableRetriever
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import KnowledgeRetriever
from cardio_materno.bootstrap.settings import RagSettings

MSG_RAG_DISABLED = "RAG desactivado (RAG_ENABLED=false): el asistente no dará información de salud."
MSG_RAG_UNAVAILABLE = (
    "⚠️  RAG no disponible: {error}\n"
    "    El asistente seguirá, pero sin información de salud (se abstendrá). "
    "Para construir el índice: python run_build_kb_index.py"
)
MSG_RAG_READY = "Base de conocimiento: {count} registros · índice con '{model}'"


@dataclass(frozen=True)
class RagSetup:
    """Resultado de preparar el RAG.

    Attributes:
        retriever: Buscador de evidencia (nulo si el RAG no está disponible).
        policy: Política de evidencia.
        status_message: Mensaje informativo para mostrar al arrancar.
    """

    retriever: KnowledgeRetriever
    policy: EvidencePolicy
    status_message: str


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


def setup_rag(settings: RagSettings, base_url: str) -> RagSetup:
    """Prepara el buscador; si algo falta, devuelve un buscador nulo con un aviso claro.

    Raises:
        KnowledgeBaseError: Si la política de evidencia no existe o es inválida.
    """
    policy = load_policy(settings.policy_file)
    if not settings.enabled:
        return RagSetup(UnavailableRetriever(), policy, MSG_RAG_DISABLED)
    try:
        retriever, count = _build_retriever(settings, base_url, policy)
    except (KnowledgeBaseError, LanguageModelError) as error:
        return RagSetup(UnavailableRetriever(), policy, MSG_RAG_UNAVAILABLE.format(error=error))
    ready = MSG_RAG_READY.format(count=count, model=settings.embed_model)
    return RagSetup(retriever, policy, ready)


def _build_retriever(
    settings: RagSettings, base_url: str, policy: EvidencePolicy
) -> tuple[HybridRetriever, int]:
    """Carga la base y el índice, verifica el modelo y crea el buscador híbrido."""
    entries = load_entries(settings.entries_file)
    index = load_index(settings.index_dir)
    embedder = build_embedder(settings, base_url)
    embedder.verify_ready()
    return HybridRetriever(entries, index, embedder, policy), len(entries)
