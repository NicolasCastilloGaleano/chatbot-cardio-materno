"""Puerto de persistencia de hilos y mensajes."""

from typing import Protocol

from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ChatMessage, ConversationThread


class ThreadRepository(Protocol):
    """Guarda y recupera hilos conversacionales y sus mensajes."""

    def save_thread(self, thread: ConversationThread) -> None:
        """Crea o actualiza un hilo (sin tocar sus mensajes)."""
        ...

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Devuelve el hilo con ese identificador, o None si no existe."""
        ...

    def append_message(self, message: ChatMessage) -> None:
        """Agrega un mensaje al hilo indicado en `message.thread_id`.

        Raises:
            KeyError: Si el hilo no existe.
        """
        ...

    def append_alert(self, thread_id: str, alert: Alert) -> None:
        """Registra una alerta en el hilo indicado.

        Raises:
            KeyError: Si el hilo no existe.
        """
        ...

    def recent_messages(self, thread_id: str, limit: int) -> list[ChatMessage]:
        """Devuelve los últimos `limit` mensajes del hilo, del más antiguo al más reciente."""
        ...
