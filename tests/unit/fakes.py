"""Dobles de prueba compartidos para los puertos de la aplicación."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from cardio_materno.domain.conversation import ChatMessage, ConversationThread


def agent_json(
    reply: str = "respuesta",
    thread_action: str = "continuar",
    domain: str = "materno_infantil",
    summary: str = "resumen",
) -> dict[str, Any]:
    """Construye una respuesta JSON válida del agente."""
    return {"thread_action": thread_action, "domain": domain, "summary": summary, "reply": reply}


class ScriptedLanguageModel:
    """LLM falso que devuelve respuestas predefinidas y registra el contexto recibido."""

    def __init__(self, *responses: dict[str, Any] | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class InMemoryThreadRepository:
    """Repositorio de hilos en memoria para pruebas."""

    def __init__(self) -> None:
        self.threads: dict[str, ConversationThread] = {}
        self.messages: dict[str, list[ChatMessage]] = {}

    def save_thread(self, thread: ConversationThread) -> None:
        self.threads[thread.id] = thread
        self.messages.setdefault(thread.id, [])

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        return self.threads.get(thread_id)

    def append_message(self, message: ChatMessage) -> None:
        if message.thread_id not in self.messages:
            raise KeyError(message.thread_id)
        self.messages[message.thread_id].append(message)

    def recent_messages(self, thread_id: str, limit: int) -> list[ChatMessage]:
        return self.messages.get(thread_id, [])[-limit:] if limit > 0 else []


class FakeClock:
    """Reloj que avanza un segundo en cada llamada."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.current += timedelta(seconds=1)
        return self.current


class SequentialIds:
    """Generador de identificadores predecibles: hilo-1, hilo-2…"""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"hilo-{self.count}"
