"""Construcción del índice vectorial a partir de `entries.jsonl` (ADR 0008)."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from cardio_materno.adapters.outbound.rag.knowledge_files import file_digest
from cardio_materno.adapters.outbound.rag.vector_index import IndexManifest, save_index
from cardio_materno.application.ports.embedder import Embedder
from cardio_materno.domain.knowledge import KnowledgeEntry

DEFAULT_CHUNK = 64

Progress = Callable[[int, int], None]


def build_index(
    entries: Sequence[KnowledgeEntry],
    entries_path: Path,
    embedder: Embedder,
    output_dir: Path,
    progress: Progress = lambda done, total: None,
) -> IndexManifest:
    """Calcula los embeddings de todos los registros y guarda el índice.

    Args:
        entries: Registros de la base.
        entries_path: Archivo de la base (para guardar su hash en el manifiesto).
        embedder: Modelo de embeddings.
        output_dir: Carpeta del índice.
        progress: Función que recibe (procesados, total) tras cada bloque de DEFAULT_CHUNK.

    Returns:
        El manifiesto del índice guardado.

    Raises:
        LanguageModelError: Si el modelo de embeddings falla.
    """
    vectors: list[list[float]] = []
    for start in range(0, len(entries), DEFAULT_CHUNK):
        block = entries[start : start + DEFAULT_CHUNK]
        vectors.extend(embedder.embed([entry.embedding_text for entry in block]))
        progress(len(vectors), len(entries))
    matrix = np.asarray(vectors, dtype=np.float32)
    manifest = make_manifest(embedder.model, matrix.shape[1], entries_path, len(entries))
    save_index(output_dir, [entry.id for entry in entries], matrix, manifest)
    return manifest


def make_manifest(
    embed_model: str, dimensions: int, entries_path: Path, count: int
) -> IndexManifest:
    """Metadatos del índice recién construido."""
    return IndexManifest(
        embed_model=embed_model,
        dimensions=dimensions,
        entries_sha256=file_digest(entries_path),
        created_at=datetime.now(UTC).isoformat(),
        count=count,
    )
