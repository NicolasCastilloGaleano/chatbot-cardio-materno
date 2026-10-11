"""Puerto del modelo de embeddings."""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Convierte textos en vectores numéricos."""

    @property
    def model(self) -> str:
        """Nombre del modelo de embeddings (para verificar compatibilidad con el índice)."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden.

        Raises:
            LanguageModelError: Si el servicio de embeddings falla.
        """
        ...
