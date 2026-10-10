"""Pruebas del chat de consola con entrada y salida simuladas."""

from collections.abc import Sequence

from cardio_materno.adapters.inbound.console.console_chat import (
    GOODBYE_TEXT,
    WELCOME_TEXT,
    ConsoleChat,
)
from cardio_materno.application.chat_service import ChatService
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ChatMessage


class EchoModel:
    """Modelo falso que repite el último mensaje o falla si se le indica."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on

    def reply(self, messages: Sequence[ChatMessage]) -> str:
        last = messages[-1].content
        if last == self.fail_on:
            raise LanguageModelError("Ollama tardó demasiado")
        return f"eco: {last}"


def run_console(inputs: list[str], model: EchoModel | None = None) -> list[str]:
    """Ejecuta la consola con las entradas dadas y devuelve todo lo mostrado."""
    pending = iter(inputs)
    output: list[str] = []

    def read(_prompt: str) -> str:
        try:
            return next(pending)
        except StopIteration:
            raise EOFError from None

    ConsoleChat(ChatService(model or EchoModel(), "sys"), read=read, write=output.append).run()
    return output


def test_shows_answer_and_exits_with_salir() -> None:
    output = run_console(["hola", "salir", "no se lee"])

    assert output[0] == WELCOME_TEXT
    assert "Asistente: eco: hola" in output
    assert output[-1] == GOODBYE_TEXT
    assert not any("no se lee" in line for line in output)


def test_empty_lines_are_ignored() -> None:
    output = run_console(["   ", "hola", "SALIR"])

    assert sum(line.startswith("Asistente:") for line in output) == 1


def test_model_error_is_shown_and_chat_continues() -> None:
    output = run_console(["falla", "hola", "salir"], EchoModel(fail_on="falla"))

    assert any("Ollama tardó demasiado" in line for line in output)
    assert "Asistente: eco: hola" in output


def test_end_of_input_closes_gracefully() -> None:
    output = run_console(["hola"])

    assert output[-1] == GOODBYE_TEXT
