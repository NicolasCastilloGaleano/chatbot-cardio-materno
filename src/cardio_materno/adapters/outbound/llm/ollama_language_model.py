"""Adaptador de Ollama para el puerto LanguageModel (ADR 0005).

Usa `/api/chat` con salida restringida por un JSON Schema. El transporte HTTP y la
traducción de errores viven en `ollama_http.py`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

from cardio_materno.adapters.outbound.llm.ollama_http import (
    MSG_INVALID_RESPONSE,
    OllamaHttpClient,
    Opener,
    parse_json_body,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage

CHAT_ENDPOINT = "/api/chat"


@dataclass(frozen=True)
class OllamaSettings:
    """Configuración del servidor y del modelo de Ollama.

    Attributes:
        base_url: URL del servidor (p. ej., http://127.0.0.1:11434), sin "/" final.
        model: Nombre del modelo tal como aparece en `ollama list`.
        timeout_seconds: Tiempo máximo de espera por solicitud.
        temperature: Aleatoriedad de la generación (0 = determinista).
        num_ctx: Tamaño de la ventana de contexto en tokens.
    """

    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    num_ctx: int


class OllamaLanguageModel:
    """Implementación del puerto LanguageModel sobre un servidor Ollama."""

    def __init__(self, settings: OllamaSettings, opener: Opener = urlopen) -> None:
        """Crea el adaptador.

        Args:
            settings: Configuración de Ollama.
            opener: Función que ejecuta la solicitud HTTP (se reemplaza en las pruebas).
        """
        self._settings = settings
        self._http = OllamaHttpClient(settings.base_url, settings.timeout_seconds, opener)

    @property
    def model(self) -> str:
        """Modelo que usa este adaptador."""
        return self._settings.model

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Pide a Ollama una respuesta en JSON restringida por un JSON Schema.

        Args:
            messages: Conversación a enviar, empezando por los mensajes de sistema.
            schema: JSON Schema que Ollama usa para restringir la salida (`format`).

        Returns:
            El objeto JSON generado por el modelo.

        Raises:
            LanguageModelError: Si Ollama no responde, falla o no devuelve un objeto JSON.
        """
        response = self._http.post(
            CHAT_ENDPOINT, build_chat_payload(self._settings, messages, schema)
        )
        return parse_json_body(extract_content(response).encode("utf-8"))

    def verify_ready(self) -> None:
        """Comprueba que Ollama responde y que el modelo configurado está instalado.

        Raises:
            LanguageModelError: Si Ollama no responde o falta el modelo.
        """
        self._http.ensure_model_installed(self._settings.model)


def build_chat_payload(
    settings: OllamaSettings, messages: Sequence[ChatMessage], schema: dict[str, Any]
) -> dict[str, Any]:
    """Construye el cuerpo de la solicitud a `/api/chat` (sin streaming, salida JSON).

    Args:
        settings: Configuración con el modelo y las opciones de generación.
        messages: Conversación a enviar.
        schema: JSON Schema que restringe la salida del modelo.

    Returns:
        Diccionario listo para serializar como JSON.
    """
    return {
        "model": settings.model,
        "messages": [{"role": str(m.role), "content": m.content} for m in messages],
        "stream": False,
        "format": schema,
        "options": {"temperature": settings.temperature, "num_ctx": settings.num_ctx},
    }


def extract_content(response: dict[str, Any]) -> str:
    """Obtiene el texto de la respuesta de `/api/chat`.

    Raises:
        LanguageModelError: Si la respuesta no trae contenido.
    """
    message = response.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise LanguageModelError(MSG_INVALID_RESPONSE)
    return content.strip()
