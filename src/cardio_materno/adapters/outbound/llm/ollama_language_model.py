"""Adaptador de Ollama para el puerto LanguageModel (ADR 0005).

Usa la API HTTP local de Ollama (`/api/chat` y `/api/tags`) solo con la librería
estándar, para no requerir dependencias en el PC de pruebas.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage

CHAT_ENDPOINT = "/api/chat"
TAGS_ENDPOINT = "/api/tags"
DEFAULT_TAG = ":latest"
MAX_ERROR_DETAIL_CHARS = 300

MSG_UNREACHABLE = (
    "No se pudo conectar con Ollama en {url}. Verifica que Ollama esté abierto "
    "(o ejecuta `ollama serve`) y que OLLAMA_BASE_URL sea correcta."
)
MSG_TIMEOUT = (
    "Ollama tardó más de {seconds:g} s en responder. "
    "Intenta de nuevo o sube OLLAMA_TIMEOUT_SECONDS."
)
MSG_HTTP_ERROR = "Ollama respondió con error HTTP {code}: {detail}"
MSG_INVALID_RESPONSE = "Ollama devolvió una respuesta inesperada o vacía."
MSG_MODEL_MISSING = "El modelo '{model}' no está instalado. Descárgalo con: ollama pull {model}"

Opener = Callable[..., HTTPResponse]


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
        self._opener = opener

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
        payload = build_chat_payload(self._settings, messages, schema)
        response = self._request(CHAT_ENDPOINT, payload)
        return parse_json_body(extract_content(response).encode("utf-8"))

    def verify_ready(self) -> None:
        """Comprueba que Ollama responde y que el modelo configurado está instalado.

        Raises:
            LanguageModelError: Si Ollama no responde o falta el modelo.
        """
        tags = self._request(TAGS_ENDPOINT)
        if not is_model_installed(self._settings.model, installed_models(tags)):
            raise LanguageModelError(MSG_MODEL_MISSING.format(model=self._settings.model))

    def _request(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ejecuta una solicitud JSON y traduce los errores a LanguageModelError."""
        request = build_request(self._settings.base_url + endpoint, payload)
        try:
            with self._opener(request, timeout=self._settings.timeout_seconds) as response:
                return parse_json_body(response.read())
        except HTTPError as error:
            raise LanguageModelError(describe_http_error(error)) from error
        except TimeoutError as error:
            raise LanguageModelError(self._timeout_message()) from error
        except URLError as error:
            raise LanguageModelError(self._url_error_message(error)) from error

    def _timeout_message(self) -> str:
        """Mensaje para cuando Ollama no responde a tiempo."""
        return MSG_TIMEOUT.format(seconds=self._settings.timeout_seconds)

    def _url_error_message(self, error: URLError) -> str:
        """Distingue un timeout de conexión de un servidor inalcanzable."""
        if isinstance(error.reason, TimeoutError):
            return self._timeout_message()
        return MSG_UNREACHABLE.format(url=self._settings.base_url)


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


def build_request(url: str, payload: dict[str, Any] | None) -> Request:
    """Crea una solicitud GET (sin cuerpo) o POST con cuerpo JSON en UTF-8."""
    if payload is None:
        return Request(url, method="GET")
    body = json.dumps(payload).encode("utf-8")
    return Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")


def parse_json_body(raw: bytes) -> dict[str, Any]:
    """Decodifica el cuerpo JSON de una respuesta.

    Raises:
        LanguageModelError: Si el cuerpo no es un objeto JSON válido.
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LanguageModelError(MSG_INVALID_RESPONSE) from error
    if not isinstance(data, dict):
        raise LanguageModelError(MSG_INVALID_RESPONSE)
    return data


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


def installed_models(tags: dict[str, Any]) -> set[str]:
    """Lista los nombres de los modelos que reporta `/api/tags`."""
    models = tags.get("models", [])
    return {item["name"] for item in models if isinstance(item, dict) and "name" in item}


def is_model_installed(model: str, available: set[str]) -> bool:
    """Indica si el modelo está instalado; sin etiqueta se asume `:latest`."""
    return model in available or model + DEFAULT_TAG in available


def describe_http_error(error: HTTPError) -> str:
    """Convierte un error HTTP de Ollama en un mensaje legible y acotado."""
    detail = error.read().decode("utf-8", errors="replace")[:MAX_ERROR_DETAIL_CHARS]
    return MSG_HTTP_ERROR.format(code=error.code, detail=detail)
