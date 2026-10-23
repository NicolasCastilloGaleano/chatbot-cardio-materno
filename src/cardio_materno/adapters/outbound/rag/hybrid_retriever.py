"""Buscador híbrido: vectores + BM25 fusionados por ranking (portado del piloto, ADR 0008).

1. Busca por similitud coseno en el índice vectorial (la consulta lleva la instrucción Qwen3).
2. Busca por términos con BM25.
3. Fusiona ambos rankings con Reciprocal Rank Fusion (RRF).
4. Solo la similitud vectorial certifica relevancia: un registro encontrado únicamente por
   términos puede ordenar, pero nunca califica como evidencia.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

from cardio_materno.adapters.outbound.rag.bm25 import Bm25Index, tokenize
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError, file_digest
from cardio_materno.adapters.outbound.rag.vector_index import VectorIndex
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.embedder import Embedder
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.knowledge import (
    EvidenceItem,
    KnowledgeEntry,
    RetrievalResult,
    RetrievalStatus,
)

LABEL_TEMPLATE = "E{number}"


class HybridRetriever:
    """Implementación del puerto KnowledgeRetriever sobre el índice propio."""

    def __init__(
        self,
        entries: Sequence[KnowledgeEntry],
        index: VectorIndex,
        embedder: Embedder,
        policy: EvidencePolicy,
    ) -> None:
        """Crea el buscador y verifica que el índice corresponda a la base y al modelo.

        Raises:
            KnowledgeBaseError: Si el índice se construyó con otro modelo o con otra base.
        """
        check_compatibility(entries, index, embedder.model)
        self._entries = {entry.id: entry for entry in entries}
        self._index = index
        self._embedder = embedder
        self._policy = policy
        self._lexical = Bm25Index(
            {
                e.id: tokenize(f"{e.question} {e.category} {e.answer}", policy.min_token_chars)
                for e in entries
            }
        )

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        """Devuelve la evidencia que supera el umbral; UNAVAILABLE si falla el embedding."""
        text = query.text[: self._policy.max_query_chars]
        try:
            vector = self._embedder.embed([self._policy.query_instruction + text])[0]
        except LanguageModelError:
            return RetrievalResult(RetrievalStatus.UNAVAILABLE)
        allowed = self._allowed_ids(query)
        similarities = self._index.search(vector, allowed, self._policy.candidate_k)
        lexical = self._lexical_rank(text, allowed)
        return self._build_result(
            similarities, fuse_rankings([list(similarities), lexical], self._policy.rrf_k)
        )

    def _allowed_ids(self, query: EvidenceQuery) -> set[str]:
        """Registros de los dominios pedidos (todos si no se indica ninguno)."""
        return {
            entry.id
            for entry in self._entries.values()
            if not query.domains or entry.domain in query.domains
        }

    def _lexical_rank(self, text: str, allowed: Collection[str]) -> list[str]:
        """Ranking BM25 restringido a los registros permitidos."""
        ranked = self._lexical.rank(
            tokenize(text, self._policy.min_token_chars), len(self._entries)
        )
        return [item_id for item_id in ranked if item_id in allowed][: self._policy.candidate_k]

    def _build_result(self, similarities: dict[str, float], fused: list[str]) -> RetrievalResult:
        """Aplica el umbral, etiqueta la evidencia (E1, E2…) y decide el estado."""
        # Solo la similitud vectorial certifica: un registro hallado únicamente por BM25 no tiene
        # similitud y nunca califica, aunque el umbral sea 0 (p. ej., en la sonda de calibración).
        supported = [
            i for i in fused if i in similarities and similarities[i] >= self._policy.min_similarity
        ]
        items = tuple(
            EvidenceItem(
                LABEL_TEMPLATE.format(number=n), self._entries[i], round(similarities[i], 4)
            )
            for n, i in enumerate(supported[: self._policy.top_k], start=1)
        )
        status = RetrievalStatus.SUFFICIENT if items else RetrievalStatus.INSUFFICIENT
        return RetrievalResult(status, items, round(max(similarities.values(), default=0.0), 4))


def fuse_rankings(rankings: Iterable[Sequence[str]], rrf_k: float) -> list[str]:
    """Reciprocal Rank Fusion: suma 1/(k + posición) de cada ranking."""
    scores: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        for position, item_id in enumerate(ranking, start=1):
            scores[item_id] += 1 / (rrf_k + position)
    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)


def check_compatibility(
    entries: Sequence[KnowledgeEntry], index: VectorIndex, embed_model: str
) -> None:
    """Verifica que el índice se construyó con el mismo modelo y los mismos registros.

    Raises:
        KnowledgeBaseError: Si no coinciden (hay que reconstruir el índice).
    """
    if index.manifest.embed_model != embed_model:
        raise KnowledgeBaseError(
            f"El índice se construyó con '{index.manifest.embed_model}' y OLLAMA_EMBED_MODEL es "
            f"'{embed_model}'. Reconstrúyelo con: python run_build_kb_index.py"
        )
    if set(index.ids) != {entry.id for entry in entries}:
        raise KnowledgeBaseError(
            "La base de conocimiento cambió desde que se construyó el índice. "
            "Reconstrúyelo con: python run_build_kb_index.py"
        )


def check_entries_file(index: VectorIndex, entries_path: Path) -> None:
    """Verifica que el índice se construyó con este mismo archivo de la base (ADR 0016).

    Los ids de la base v2 no cambian si se edita un texto, así que comparar los ids no basta:
    se compara el hash del archivo guardado en el manifiesto.

    Raises:
        KnowledgeBaseError: Si el archivo cambió desde que se construyó el índice.
    """
    if index.manifest.entries_sha256 != file_digest(entries_path):
        raise KnowledgeBaseError(
            "El archivo de la base cambió desde que se construyó el índice (mismo conjunto de "
            "registros, distinto contenido). Reconstrúyelo con: python run_build_kb_index.py"
        )
