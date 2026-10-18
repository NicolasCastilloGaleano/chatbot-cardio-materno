"""Puerto de lectura para auditar los chats de todos los canales (HU-10, ADR 0016).

Solo lee: lista los chats (uno por usuario) y entrega sus mensajes por páginas, sobre el
orden de inserción (`seq`), con el hilo y las alertas de cada turno.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ChatMessage, ConversationThread
from cardio_materno.domain.user import Channel


@dataclass(frozen=True)
class ChatSummary:
    """Resumen de un chat para la lista.

    Attributes:
        user_id: Identificador del chat (el del usuario).
        channel: Canal del chat.
        created_at: Primer contacto.
        last_seen_at: Último mensaje de la persona o del equipo.
        message_count: Mensajes guardados (preguntas y respuestas).
        has_open_thread: Si hay un hilo abierto.
        live_session_at: Desde cuándo una consola tiene abierto el chat (None si ninguna).
    """

    user_id: str
    channel: Channel
    created_at: datetime
    last_seen_at: datetime
    message_count: int
    has_open_thread: bool
    live_session_at: datetime | None = None


@dataclass(frozen=True)
class ChatEntry:
    """Un mensaje del chat con su posición, su hilo y las alertas de su turno.

    Attributes:
        seq: Posición del mensaje en la base (crece con cada mensaje).
        message: El mensaje, con su traza si es una respuesta del agente.
        thread: Hilo al que pertenece.
        alerts: Alertas del turno (solo en las respuestas del asistente).
    """

    seq: int
    message: ChatMessage
    thread: ConversationThread
    alerts: tuple[Alert, ...] = ()


@dataclass(frozen=True)
class ChatPage:
    """Página de mensajes en orden cronológico.

    Attributes:
        entries: Mensajes, del más antiguo al más reciente.
        next_before: `seq` para pedir la página anterior, o None si no hay más.
    """

    entries: tuple[ChatEntry, ...]
    next_before: int | None = None


class ChatAudit(Protocol):
    """Lectura de chats para la auditoría."""

    def list_chats(self, channel: Channel | None, limit: int, offset: int) -> list[ChatSummary]:
        """Chats del más reciente al más antiguo, opcionalmente de un solo canal."""
        ...

    def get_chat(self, user_id: str) -> ChatSummary | None:
        """Resumen de un chat, o None si no existe."""
        ...

    def message_page(self, user_id: str, before: int | None, limit: int) -> ChatPage:
        """Los `limit` mensajes anteriores a `before` (o los más recientes si es None)."""
        ...

    def messages_after(self, user_id: str, after: int, limit: int) -> ChatPage:
        """Hasta `limit` mensajes posteriores a `after` (para la actualización automática)."""
        ...

    def pending_inbound(self, user_id: str) -> int:
        """Mensajes del canal recibidos y aún en proceso (su texto todavía no está guardado)."""
        ...
