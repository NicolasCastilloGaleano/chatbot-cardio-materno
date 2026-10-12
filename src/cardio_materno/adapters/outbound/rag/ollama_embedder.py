"""Embeddings con Ollama (`/api/embed`) para el puerto Embedder (ADR 0008)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

from cardio_materno.adapters.outbound.llm.ollama_http import (
    MSG_INVALID_RESPONSE,
    OllamaHttpClient,
    OllamaTimeoutError,
    Opener,
)
from cardio_materno.adapters.outbound.llm.ollama_language_model import DEFAULT_KEEP_ALIVE
from cardio_materno.application.errors import LanguageModelError

EMBED_ENDPOINT = "/api/embed"
MIN_SPLITTABLE_BATCH = 2

WARM_UP_TEXT = "hola"


@dataclass(frozen=True)
class EmbedderSettings:
    """Configuración del modelo de embeddings.

    Attributes:
        base_url: URL del servidor Ollama.
        model: Modelo de embeddings (p. ej., qwen3-embedding:8b).
        timeout_seconds: Tiempo máximo por solicitud.
        batch_size: Textos por solicitud.
        keep_alive: Tiempo que Ollama mantiene el modelo cargado tras cada solicitud.
        num_gpu: Capas en GPU (0 = el embedder corre en CPU y deja la GPU al LLM);
            None = decide Ollama.
    """

    base_url: str
    model: str
    timeout_seconds: float
    batch_size: int
    keep_alive: str = DEFAULT_KEEP_ALIVE
    num_gpu: int | None = None


class OllamaEmbedder:
    """Calcula embeddings por lotes; si un lote excede el tiempo, lo parte en dos."""

    def __init__(self, settings: EmbedderSettings, opener: Opener = urlopen) -> None:
        """Crea el adaptador.

        Args:
            settings: Configuración del modelo de embeddings.
            opener: Función que ejecuta la solicitud HTTP (se reemplaza en las pruebas).
        """
        self._settings = settings
        self._http = OllamaHttpClient(settings.base_url, settings.timeout_seconds, opener)

    @property
    def model(self) -> str:
        """Modelo de embeddings configurado."""
        return self._settings.model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden.

        Raises:
            LanguageModelError: Si Ollama falla o devuelve una cantidad inesperada de vectores.
        """
        size = max(1, self._settings.batch_size)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), size):
            vectors.extend(self._embed_batch(list(texts[start : start + size])))
        return vectors

    def verify_ready(self) -> None:
        """Verifica que Ollama responde y que el modelo de embeddings está instalado."""
        self._http.ensure_model_installed(self._settings.model)

    def warm_up(self) -> None:
        """Embebe un texto corto para cargar el modelo antes del primer turno.

        Raises:
            LanguageModelError: Si Ollama falla.
        """
        self.embed([WARM_UP_TEXT])

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Embebe un lote; ante un timeout con varios textos, reintenta en dos mitades."""
        try:
            response = self._http.post(EMBED_ENDPOINT, build_embed_payload(self._settings, batch))
        except OllamaTimeoutError:
            if len(batch) < MIN_SPLITTABLE_BATCH:
                raise
            half = len(batch) // 2
            return self._embed_batch(batch[:half]) + self._embed_batch(batch[half:])
        return parse_embeddings(response, expected=len(batch))


def build_embed_payload(settings: EmbedderSettings, batch: list[str]) -> dict[str, Any]:
    """Cuerpo de `/api/embed`; agrega `options.num_gpu` solo si está configurado."""
    payload: dict[str, Any] = {
        "model": settings.model,
        "input": batch,
        "keep_alive": settings.keep_alive,
    }
    if settings.num_gpu is not None:
        payload["options"] = {"num_gpu": settings.num_gpu}
    return payload


def parse_embeddings(response: dict[str, Any], expected: int) -> list[list[float]]:
    """Extrae los vectores de la respuesta de `/api/embed`.

    Raises:
        LanguageModelError: Si no hay vectores o la cantidad no coincide.
    """
    embeddings = response.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != expected:
        raise LanguageModelError(MSG_INVALID_RESPONSE)
    return [[float(value) for value in vector] for vector in embeddings]
