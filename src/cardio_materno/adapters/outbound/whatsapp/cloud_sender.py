"""Envío de mensajes por WhatsApp Cloud API (Graph API de Meta, ADR 0014).

Solo usa la biblioteca estándar, igual que el cliente de Ollama. Los errores se traducen a
`ChannelDeliveryError` con el código y la descripción de Meta, sin el número ni el texto.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cardio_materno.application.errors import ChannelDeliveryError

DEFAULT_GRAPH_URL = "https://graph.facebook.com"
MESSAGING_PRODUCT = "whatsapp"
MAX_ERROR_DETAIL_CHARS = 300

MSG_HTTP_ERROR = "WhatsApp respondió con error HTTP {code}: {detail}"
MSG_UNREACHABLE = "No se pudo conectar con WhatsApp Cloud API ({reason})."
MSG_INVALID_RESPONSE = "WhatsApp devolvió una respuesta inesperada."


class HttpResponse(Protocol):
    """Respuesta HTTP mínima (la cumple la de `urlopen`)."""

    def read(self) -> bytes:
        """Devuelve el cuerpo completo."""
        ...

    def __enter__(self) -> "HttpResponse":
        """Permite usar la respuesta con `with`."""
        ...

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        """Libera la conexión."""
        ...


Opener = Callable[..., HttpResponse]


@dataclass(frozen=True)
class CloudApiSettings:
    """Datos de la app de Meta.

    Attributes:
        token: Token de acceso (`WHATSAPP_TOKEN`).
        phone_number_id: Identificador del número emisor (`WHATSAPP_PHONE_NUMBER_ID`).
        api_version: Versión de la Graph API (`WHATSAPP_API_VERSION`, p. ej. "v23.0").
        timeout_seconds: Tiempo máximo por solicitud.
        base_url: URL de la Graph API (se cambia solo en pruebas).
    """

    token: str
    phone_number_id: str
    api_version: str
    timeout_seconds: float
    base_url: str = DEFAULT_GRAPH_URL


class WhatsAppCloudSender:
    """Implementación de MessageSender sobre WhatsApp Cloud API."""

    def __init__(self, settings: CloudApiSettings, opener: Opener = urlopen) -> None:
        """Crea el emisor.

        Args:
            settings: Token, número emisor, versión y tiempo de espera.
            opener: Ejecuta la solicitud HTTP (se reemplaza en las pruebas).
        """
        self._settings = settings
        self._opener = opener
        self._url = (
            f"{settings.base_url}/{settings.api_version}/{settings.phone_number_id}/messages"
        )

    def send_text(self, reply_to: str, text: str) -> str:
        """Envía un mensaje de texto y devuelve su identificador (wamid).

        Raises:
            ChannelDeliveryError: Si Meta rechaza el envío o no responde.
        """
        response = self._post(text_payload(reply_to, text))
        return sent_message_id(response)

    def acknowledge(self, reply_to: str, channel_message_id: str) -> None:
        """Marca el mensaje como leído y muestra "escribiendo…".

        Raises:
            ChannelDeliveryError: Si Meta rechaza la solicitud.
        """
        self._post(read_payload(channel_message_id))

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Envía el POST autenticado y devuelve el JSON de la respuesta."""
        request = Request(
            self._url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._settings.token}",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._settings.timeout_seconds) as response:
                return parse_body(response.read())
        except HTTPError as error:
            raise ChannelDeliveryError(describe_http_error(error)) from error
        except (URLError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise ChannelDeliveryError(MSG_UNREACHABLE.format(reason=reason)) from error


def text_payload(reply_to: str, text: str) -> dict[str, Any]:
    """Cuerpo de un mensaje de texto."""
    return {
        "messaging_product": MESSAGING_PRODUCT,
        "recipient_type": "individual",
        "to": reply_to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }


def read_payload(channel_message_id: str) -> dict[str, Any]:
    """Cuerpo para marcar como leído con indicador de escritura."""
    return {
        "messaging_product": MESSAGING_PRODUCT,
        "status": "read",
        "message_id": channel_message_id,
        "typing_indicator": {"type": "text"},
    }


def parse_body(raw: bytes) -> dict[str, Any]:
    """Decodifica el JSON de la respuesta.

    Raises:
        ChannelDeliveryError: Si no es un objeto JSON.
    """
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ChannelDeliveryError(MSG_INVALID_RESPONSE) from error
    if not isinstance(data, dict):
        raise ChannelDeliveryError(MSG_INVALID_RESPONSE)
    return data


def sent_message_id(response: dict[str, Any]) -> str:
    """Identificador del mensaje enviado (`messages[0].id`).

    Raises:
        ChannelDeliveryError: Si la respuesta no lo trae.
    """
    messages = response.get("messages")
    if isinstance(messages, list) and messages and isinstance(messages[0], dict):
        message_id = messages[0].get("id")
        if isinstance(message_id, str) and message_id:
            return message_id
    raise ChannelDeliveryError(MSG_INVALID_RESPONSE)


def describe_http_error(error: HTTPError) -> str:
    """Error de Meta legible: código HTTP más `error.code` y `error.message` del cuerpo."""
    raw = error.read().decode("utf-8", errors="replace")
    try:
        detail_data = json.loads(raw).get("error", {})
        detail = f"{detail_data.get('code', '')} {detail_data.get('message', '')}".strip()
    except (json.JSONDecodeError, AttributeError):
        detail = raw
    return MSG_HTTP_ERROR.format(code=error.code, detail=detail[:MAX_ERROR_DETAIL_CHARS])
