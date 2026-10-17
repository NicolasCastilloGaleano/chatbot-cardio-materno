"""Pruebas del envío por WhatsApp Cloud API con un servidor simulado (ADR 0014)."""

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from cardio_materno.adapters.outbound.whatsapp.cloud_sender import (
    CloudApiSettings,
    WhatsAppCloudSender,
)
from cardio_materno.application.errors import ChannelDeliveryError

SETTINGS = CloudApiSettings("token-secreto", "123456", "v23.0", 5.0)
WA_ID = "573000000001"


class FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class RecordingOpener:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return FakeResponse(self.response)

    def body(self, index: int = 0) -> dict[str, Any]:
        data = self.requests[index].data
        assert isinstance(data, bytes)
        result: dict[str, Any] = json.loads(data)
        return result


def http_error(code: int, body: dict[str, Any]) -> HTTPError:
    return HTTPError("url", code, "error", {}, io.BytesIO(json.dumps(body).encode()))  # type: ignore[arg-type]


def test_send_text_posts_to_the_phone_number_and_returns_the_wamid() -> None:
    opener = RecordingOpener({"messages": [{"id": "wamid.out"}]})
    sender = WhatsAppCloudSender(SETTINGS, opener)

    message_id = sender.send_text(WA_ID, "Hola")

    request = opener.requests[0]
    assert message_id == "wamid.out"
    assert request.full_url == "https://graph.facebook.com/v23.0/123456/messages"
    assert request.get_header("Authorization") == "Bearer token-secreto"
    assert opener.body()["to"] == WA_ID
    assert opener.body()["text"] == {"preview_url": False, "body": "Hola"}


def test_acknowledge_marks_as_read_with_typing_indicator() -> None:
    opener = RecordingOpener({"success": True})

    WhatsAppCloudSender(SETTINGS, opener).acknowledge(WA_ID, "wamid.in")

    assert opener.body() == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.in",
        "typing_indicator": {"type": "text"},
    }


def test_meta_error_is_explained_without_the_message_text() -> None:
    error = http_error(400, {"error": {"code": 131030, "message": "Recipient not in allowed list"}})
    sender = WhatsAppCloudSender(SETTINGS, RecordingOpener(error))

    with pytest.raises(ChannelDeliveryError) as raised:
        sender.send_text(WA_ID, "texto privado")

    assert "131030" in str(raised.value) and "allowed list" in str(raised.value)
    assert "texto privado" not in str(raised.value) and WA_ID not in str(raised.value)


def test_network_error_and_unexpected_response_raise_delivery_error() -> None:
    offline = WhatsAppCloudSender(SETTINGS, RecordingOpener(URLError("sin red")))
    odd = WhatsAppCloudSender(SETTINGS, RecordingOpener({"messages": []}))

    with pytest.raises(ChannelDeliveryError):
        offline.send_text(WA_ID, "x")
    with pytest.raises(ChannelDeliveryError):
        odd.send_text(WA_ID, "x")
