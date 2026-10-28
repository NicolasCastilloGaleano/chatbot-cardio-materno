"""Adaptador de Ollama para el puerto LanguageModel (ADR 0005).

Usa `/api/chat` con salida restringida por un JSON Schema. El transporte HTTP y la
traducción de errores viven en `ollama_http.py`.
"""

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.request import urlopen

from cardio_materno.adapters.outbound.llm.ollama_http import (
    MSG_INVALID_RESPONSE,
    OllamaHttpClient,
    OllamaInvalidResponseError,
    Opener,
    parse_json_body,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage
from cardio_materno.domain.trace import ModelUsage

logger = logging.getLogger(__name__)
CHAT_ENDPOINT = "/api/chat"
# Una respuesta vacía o un JSON inválido suelen ser fallos intermitentes: se reintenta una vez.
# No se reintenta un tiempo de espera agotado (duplicaría la espera) ni un corte por límite.
INVALID_RESPONSE_RETRIES = 1
NANOSECONDS_PER_SECOND = 1_000_000_000
USAGE_DECIMALS = 2
MSG_RETRY_LOG = "Ollama (%s) devolvió una respuesta vacía o inválida; se reintenta (%d/%d)."
DONE_REASON_LENGTH = "length"
MSG_CUT_BY_LIMIT = (
    "Ollama cortó la respuesta por el límite de contexto o de tokens. Sube "
    "OLLAMA_<ETAPA>_NUM_CTX o OLLAMA_<ETAPA>_NUM_PREDICT (ANALYSIS o REPLY) en el .env."
)
DEFAULT_KEEP_ALIVE = "30m"


@dataclass(frozen=True)
class OllamaSettings:
    """Configuración del servidor y del modelo de Ollama.

    Attributes:
        base_url: URL del servidor (p. ej., http://127.0.0.1:11434), sin "/" final.
        model: Nombre del modelo tal como aparece en `ollama list`.
        timeout_seconds: Tiempo máximo de espera por solicitud.
        temperature: Aleatoriedad de la generación (0 = determinista).
        num_ctx: Tamaño de la ventana de contexto en tokens.
        keep_alive: Tiempo que Ollama mantiene el modelo cargado tras cada solicitud
            (p. ej., "30m"); evita recargarlo en cada turno.
        num_predict: Máximo de tokens que puede generar (None = sin límite). Evita respuestas
            desbocadas, que en un modelo que corre en parte en CPU cuestan segundos por token.
        think: Activa o desactiva el razonamiento de los modelos que lo tienen (p. ej., qwen3);
            None = no se envía y decide el modelo.
    """

    base_url: str
    model: str
    timeout_seconds: float
    temperature: float
    num_ctx: int
    keep_alive: str = DEFAULT_KEEP_ALIVE
    num_predict: int | None = None
    think: bool | None = None


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
        # Por hilo de ejecución: la web y WhatsApp atienden varios turnos a la vez.
        self._last = threading.local()

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

        Si la respuesta llega vacía o no es un objeto JSON, se reintenta una vez.

        Raises:
            LanguageModelError: Si Ollama no responde, falla o no devuelve un objeto JSON
                después del reintento.
        """
        payload = build_chat_payload(self._settings, messages, schema)
        for attempt in range(1, INVALID_RESPONSE_RETRIES + 1):
            try:
                return self._complete_once(payload)
            except OllamaInvalidResponseError as error:
                logger.warning(
                    MSG_RETRY_LOG, self._settings.model, attempt, INVALID_RESPONSE_RETRIES
                )
                logger.debug("Detalle del fallo: %s", error)
        return self._complete_once(payload)

    def _complete_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Una solicitud a `/api/chat` y su objeto JSON; guarda el uso que informa Ollama."""
        response = self._http.post(CHAT_ENDPOINT, payload)
        data = parse_json_body(extract_content(response).encode("utf-8"))
        self._last.usage = usage_from(response)
        return data

    def last_usage(self) -> ModelUsage | None:
        """Tokens y tiempos de la última llamada exitosa en este hilo de ejecución."""
        usage: ModelUsage | None = getattr(self._last, "usage", None)
        return usage

    def warm_up(self) -> None:
        """Carga el modelo en memoria sin generar nada, para que el primer turno no espere.

        Raises:
            LanguageModelError: Si Ollama no responde o falla.
        """
        self._http.post(CHAT_ENDPOINT, build_warm_up_payload(self._settings))

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
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": [{"role": str(m.role), "content": m.content} for m in messages],
        "stream": False,
        "format": schema,
        "keep_alive": settings.keep_alive,
        "options": build_options(settings),
    }
    if settings.think is not None:
        payload["think"] = settings.think
    return payload


def build_options(settings: OllamaSettings) -> dict[str, Any]:
    """Opciones de generación; las mismas en las consultas y en el precalentamiento."""
    options: dict[str, Any] = {"temperature": settings.temperature, "num_ctx": settings.num_ctx}
    if settings.num_predict is not None:
        options["num_predict"] = settings.num_predict
    return options


def build_warm_up_payload(settings: OllamaSettings) -> dict[str, Any]:
    """Solicitud sin mensajes: Ollama solo carga el modelo y lo mantiene `keep_alive`.

    Lleva las mismas opciones que las consultas: si `num_ctx` cambiara, Ollama volvería a
    cargar el modelo en la primera consulta real (el primer turno seguiría siendo lento).
    """
    return {
        "model": settings.model,
        "messages": [],
        "keep_alive": settings.keep_alive,
        "options": build_options(settings),
    }


def usage_from(response: dict[str, Any]) -> ModelUsage | None:
    """Tokens y tiempos de lectura del prompt y de generación que informa `/api/chat`.

    Returns:
        El uso, o None si la respuesta no trae los contadores.
    """
    fields = ("prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration")
    values = [response.get(name) for name in fields]
    numbers = [value for value in values if isinstance(value, int)]
    if len(numbers) != len(fields):
        return None
    prompt_tokens, prompt_ns, output_tokens, output_ns = numbers
    return ModelUsage(
        "",
        prompt_tokens,
        round(prompt_ns / NANOSECONDS_PER_SECOND, USAGE_DECIMALS),
        output_tokens,
        round(output_ns / NANOSECONDS_PER_SECOND, USAGE_DECIMALS),
    )


def extract_content(response: dict[str, Any]) -> str:
    """Obtiene el texto de la respuesta de `/api/chat`.

    Raises:
        LanguageModelError: Si Ollama cortó la respuesta por el límite de contexto o de tokens
            (`done_reason` "length") o si la respuesta no trae contenido.
    """
    if response.get("done_reason") == DONE_REASON_LENGTH:
        raise LanguageModelError(MSG_CUT_BY_LIMIT)
    message = response.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OllamaInvalidResponseError(MSG_INVALID_RESPONSE)
    return content.strip()
