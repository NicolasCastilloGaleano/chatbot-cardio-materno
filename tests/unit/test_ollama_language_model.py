"""Pruebas del adaptador de Ollama con un `opener` simulado (no requiere Ollama)."""

import io
import json
from dataclasses import replace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from cardio_materno.adapters.outbound.llm.ollama_http import is_model_installed
from cardio_materno.adapters.outbound.llm.ollama_language_model import (
    OllamaLanguageModel,
    OllamaSettings,
    build_chat_payload,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage, Role

SETTINGS = OllamaSettings(
    base_url="http://ollama.test:11434",
    model="mistral-small3.1:24b",
    timeout_seconds=5,
    temperature=0.3,
    num_ctx=4096,
)


class FakeResponse(io.BytesIO):
    """Respuesta HTTP mínima que funciona como context manager."""


class FakeOpener:
    """Simula `urlopen`: devuelve un cuerpo JSON o lanza el error indicado."""

    def __init__(self, body: Any = None, error: Exception | None = None) -> None:
        self.body = body
        self.error = error
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
        return FakeResponse(raw)


def make_model(opener: FakeOpener) -> OllamaLanguageModel:
    return OllamaLanguageModel(SETTINGS, opener=opener)


SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}}}
USER_MESSAGE = [ChatMessage(Role.USER, "hola")]


def chat_body(content: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}}


def test_complete_json_sends_schema_and_returns_parsed_object() -> None:
    opener = FakeOpener(chat_body('{"reply": "Hola"}'))
    messages = [ChatMessage(Role.SYSTEM, "sys"), ChatMessage(Role.USER, "hola", "hilo-1")]

    result = make_model(opener).complete_json(messages, SCHEMA)

    request = opener.requests[0]
    payload = json.loads(request.data)  # type: ignore[arg-type]
    assert result == {"reply": "Hola"}
    assert request.full_url == "http://ollama.test:11434/api/chat"
    assert payload["model"] == "mistral-small3.1:24b"
    assert payload["stream"] is False
    assert payload["format"] == SCHEMA
    assert payload["keep_alive"] == "30m"
    assert payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hola"},
    ]


@pytest.mark.parametrize(
    "body",
    [
        chat_body("   "),
        chat_body("esto no es json"),
        chat_body('["lista"]'),
        {"other": 1},
        b"no es json",
        ["lista"],
    ],
)
def test_complete_json_rejects_invalid_or_empty_responses(body: Any) -> None:
    with pytest.raises(LanguageModelError, match="inesperada"):
        make_model(FakeOpener(body)).complete_json(USER_MESSAGE, SCHEMA)


def test_connection_error_explains_how_to_fix() -> None:
    opener = FakeOpener(error=URLError(ConnectionRefusedError()))

    with pytest.raises(LanguageModelError, match="No se pudo conectar"):
        make_model(opener).complete_json(USER_MESSAGE, SCHEMA)


@pytest.mark.parametrize("error", [TimeoutError(), URLError(TimeoutError())])
def test_timeout_is_reported(error: Exception) -> None:
    with pytest.raises(LanguageModelError, match="tardó más de 5 s"):
        make_model(FakeOpener(error=error)).complete_json(USER_MESSAGE, SCHEMA)


def test_http_error_includes_status_and_detail() -> None:
    error = HTTPError("url", 500, "err", {}, io.BytesIO(b"model failed"))  # type: ignore[arg-type]

    with pytest.raises(LanguageModelError, match="HTTP 500: model failed"):
        make_model(FakeOpener(error=error)).complete_json(USER_MESSAGE, SCHEMA)


def test_verify_ready_passes_when_model_installed() -> None:
    opener = FakeOpener({"models": [{"name": "mistral-small3.1:24b"}]})

    make_model(opener).verify_ready()

    assert opener.requests[0].get_method() == "GET"


def test_verify_ready_reports_missing_model_with_pull_command() -> None:
    opener = FakeOpener({"models": [{"name": "otro:7b"}]})

    with pytest.raises(LanguageModelError, match="ollama pull mistral-small3.1:24b"):
        make_model(opener).verify_ready()


def test_model_without_tag_matches_latest() -> None:
    assert is_model_installed("llama3", {"llama3:latest"})
    assert not is_model_installed("llama3", {"llama3:8b"})


def test_token_limit_and_think_are_sent_only_when_configured() -> None:
    default = build_chat_payload(SETTINGS, USER_MESSAGE, SCHEMA)
    tuned = build_chat_payload(
        replace(SETTINGS, num_predict=500, think=False), USER_MESSAGE, SCHEMA
    )

    assert "num_predict" not in default["options"] and "think" not in default
    assert tuned["options"]["num_predict"] == 500 and tuned["think"] is False


def test_warm_up_loads_the_model_without_messages() -> None:
    opener = FakeOpener({"model": "mistral-small3.1:24b", "done": True, "done_reason": "load"})

    make_model(opener).warm_up()

    payload = json.loads(opener.requests[0].data)  # type: ignore[arg-type]
    assert opener.requests[0].full_url == "http://ollama.test:11434/api/chat"
    assert payload == {"model": "mistral-small3.1:24b", "messages": [], "keep_alive": "30m"}
