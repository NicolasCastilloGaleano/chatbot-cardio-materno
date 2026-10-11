"""Cliente HTTP mínimo de Ollama, compartido por el LLM y los embeddings (ADR 0005, 0008).

Solo usa la librería estándar. Traduce todos los errores a `LanguageModelError` con
mensajes en español que explican cómo solucionarlos.
"""

import json
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cardio_materno.application.errors import LanguageModelError

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


class OllamaTimeoutError(LanguageModelError):
    """Ollama no respondió dentro del tiempo configurado."""


class HttpResponse(Protocol):
    """Respuesta HTTP mínima que usa el cliente (la cumple la de `urlopen`)."""

    def read(self) -> bytes:
        """Devuelve el cuerpo completo de la respuesta."""
        ...

    def __enter__(self) -> "HttpResponse":
        """Permite usar la respuesta con `with`."""
        ...

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        """Libera la conexión al salir del bloque `with`."""
        ...


Opener = Callable[..., HttpResponse]


class OllamaHttpClient:
    """Envía solicitudes JSON a un servidor Ollama."""

    def __init__(self, base_url: str, timeout_seconds: float, opener: Opener = urlopen) -> None:
        """Crea el cliente.

        Args:
            base_url: URL del servidor, sin "/" final.
            timeout_seconds: Tiempo máximo de espera por solicitud.
            opener: Función que ejecuta la solicitud HTTP (se reemplaza en las pruebas).
        """
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Envía un POST con cuerpo JSON y devuelve el JSON de la respuesta."""
        return self._send(build_request(self._base_url + endpoint, payload))

    def get(self, endpoint: str) -> dict[str, Any]:
        """Envía un GET y devuelve el JSON de la respuesta."""
        return self._send(build_request(self._base_url + endpoint, None))

    def ensure_model_installed(self, model: str) -> None:
        """Verifica que Ollama responde y que el modelo está descargado.

        Raises:
            LanguageModelError: Si Ollama no responde o falta el modelo.
        """
        if not is_model_installed(model, installed_models(self.get(TAGS_ENDPOINT))):
            raise LanguageModelError(MSG_MODEL_MISSING.format(model=model))

    def _send(self, request: Request) -> dict[str, Any]:
        """Ejecuta la solicitud y traduce los errores a LanguageModelError."""
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                return parse_json_body(response.read())
        except HTTPError as error:
            raise LanguageModelError(describe_http_error(error)) from error
        except TimeoutError as error:
            raise OllamaTimeoutError(self._timeout_message()) from error
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise OllamaTimeoutError(self._timeout_message()) from error
            raise LanguageModelError(MSG_UNREACHABLE.format(url=self._base_url)) from error

    def _timeout_message(self) -> str:
        """Mensaje para cuando Ollama no responde a tiempo."""
        return MSG_TIMEOUT.format(seconds=self._timeout_seconds)


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
