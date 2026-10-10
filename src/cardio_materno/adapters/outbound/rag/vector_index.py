"""Índice vectorial propio en archivos (numpy), derivado de `entries.jsonl` (ADR 0008).

Archivos en el directorio del índice:
- `embeddings.npy`: matriz float32 (registros × dimensión), con filas normalizadas.
- `ids.json`: identificadores en el mismo orden que las filas.
- `manifest.json`: modelo de embeddings, dimensión, hash de la base y fecha.
"""

import json
from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError

EMBEDDINGS_FILE = "embeddings.npy"
IDS_FILE = "ids.json"
MANIFEST_FILE = "manifest.json"

FloatMatrix = npt.NDArray[np.float32]


@dataclass(frozen=True)
class IndexManifest:
    """Metadatos del índice para verificar que sigue siendo compatible.

    Attributes:
        embed_model: Modelo con el que se calcularon los vectores.
        dimensions: Dimensión de los vectores.
        entries_sha256: Hash de `entries.jsonl` cuando se construyó.
        created_at: Fecha de construcción (ISO 8601).
        count: Cantidad de registros.
    """

    embed_model: str
    dimensions: int
    entries_sha256: str
    created_at: str
    count: int


class VectorIndex:
    """Matriz de vectores normalizados con búsqueda por similitud coseno."""

    def __init__(self, ids: Sequence[str], matrix: FloatMatrix, manifest: IndexManifest) -> None:
        """Crea el índice en memoria.

        Args:
            ids: Identificadores en el orden de las filas.
            matrix: Vectores (se normalizan aquí).
            manifest: Metadatos del índice.
        """
        self.ids = tuple(ids)
        self.manifest = manifest
        self._matrix = normalize_rows(matrix)
        self._row = {item_id: row for row, item_id in enumerate(self.ids)}

    def search(
        self, vector: Sequence[float], allowed: Collection[str], limit: int
    ) -> dict[str, float]:
        """Similitud coseno de los `limit` registros más cercanos dentro de `allowed`.

        Returns:
            Identificador → similitud, de mayor a menor.
        """
        rows = [self._row[item_id] for item_id in allowed if item_id in self._row]
        if not rows:
            return {}
        query = normalize_rows(np.asarray([vector], dtype=np.float32))[0]
        scores = self._matrix[rows] @ query
        best = np.argsort(-scores)[:limit]
        return {self.ids[rows[i]]: float(scores[i]) for i in best}


def normalize_rows(matrix: FloatMatrix) -> FloatMatrix:
    """Normaliza cada fila a longitud 1 (las filas nulas quedan en cero)."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    normalized: FloatMatrix = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)
    return normalized


def save_index(
    directory: Path, ids: Sequence[str], vectors: FloatMatrix, manifest: IndexManifest
) -> None:
    """Guarda el índice en `directory` (lo crea si no existe)."""
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / EMBEDDINGS_FILE, vectors.astype(np.float32))
    (directory / IDS_FILE).write_text(json.dumps(list(ids)), encoding="utf-8")
    (directory / MANIFEST_FILE).write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")


def load_index(directory: Path) -> VectorIndex:
    """Carga el índice guardado.

    Raises:
        KnowledgeBaseError: Si falta algún archivo o los tamaños no coinciden.
    """
    try:
        manifest = IndexManifest(
            **json.loads((directory / MANIFEST_FILE).read_text(encoding="utf-8"))
        )
        ids = json.loads((directory / IDS_FILE).read_text(encoding="utf-8"))
        matrix = np.load(directory / EMBEDDINGS_FILE).astype(np.float32)
    except (FileNotFoundError, ValueError, TypeError) as error:
        raise KnowledgeBaseError(
            f"Índice de conocimiento inválido o ausente en {directory}: {error}"
        ) from error
    if matrix.shape[0] != len(ids):
        raise KnowledgeBaseError("El índice está corrupto: vectores e identificadores no coinciden")
    return VectorIndex(ids, matrix, manifest)
