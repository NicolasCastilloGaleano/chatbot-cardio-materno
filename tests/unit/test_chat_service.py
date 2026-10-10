"""Pruebas de ChatService (HU-00)."""

from collections.abc import Sequence

import pytest

from cardio_materno.application.chat_service import ChatService
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage, Role


class FakeLanguageModel:
    """Doble del puerto LanguageModel que registra las llamadas."""

    def __init__(self, answers: list[str] | None = None, error: Exception | None = None) -> None:
        self.answers = answers or ["respuesta"]
        self.error = error
        self.calls: list[list[ChatMessage]] = []

    def reply(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(list(messages))
        if self.error:
            raise self.error
        return self.answers[len(self.calls) - 1]


def test_send_returns_model_answer_with_system_prompt_first() -> None:
    model = FakeLanguageModel(["hola, ¿en qué te ayudo?"])
    service = ChatService(model, "prompt de sistema")

    answer = service.send("hola")

    assert answer == "hola, ¿en qué te ayudo?"
    assert model.calls[0] == [
        ChatMessage(Role.SYSTEM, "prompt de sistema"),
        ChatMessage(Role.USER, "hola"),
    ]


def test_send_includes_previous_turns_as_context() -> None:
    model = FakeLanguageModel(["r1", "r2"])
    service = ChatService(model, "sys")

    service.send("m1")
    service.send("m2")

    assert [m.content for m in model.calls[1]] == ["sys", "m1", "r1", "m2"]


def test_history_is_trimmed_to_max_history() -> None:
    model = FakeLanguageModel(["r1", "r2", "r3"])
    service = ChatService(model, "sys", max_history=2)

    for text in ("m1", "m2", "m3"):
        service.send(text)

    assert [m.content for m in model.calls[2]] == ["sys", "m2", "r2", "m3"]


def test_failed_reply_propagates_and_is_not_remembered() -> None:
    model = FakeLanguageModel(error=LanguageModelError("caído"))
    service = ChatService(model, "sys")

    with pytest.raises(LanguageModelError):
        service.send("m1")
    model.error = None
    model.answers = ["", "ok"]
    service.send("m2")

    assert [m.content for m in model.calls[-1]] == ["sys", "m2"]
