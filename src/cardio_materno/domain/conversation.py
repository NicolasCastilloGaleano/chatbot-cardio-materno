"""Entidades de la conversación: mensajes e hilos (HU-06, ADR 0006)."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from cardio_materno.domain.trace import ReplyTrace


class Role(StrEnum):
    """Autor de un mensaje dentro de la conversación."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Domain(StrEnum):
    """Dominio de salud al que pertenece un hilo."""

    MATERNAL_CHILD = "materno_infantil"
    CARDIOVASCULAR = "cardiovascular"
    NONE = "ninguno"


class ThreadStatus(StrEnum):
    """Estado de un hilo conversacional."""

    OPEN = "abierto"
    CLOSED = "cerrado"


@dataclass(frozen=True)
class ChatMessage:
    """Mensaje inmutable de la conversación.

    Attributes:
        role: Quién escribió el mensaje.
        content: Texto del mensaje.
        thread_id: Hilo al que pertenece (None para mensajes de contexto o de sistema).
        created_at: Momento de creación (None si no se persiste).
        trace: En mensajes del asistente, cómo se produjo la respuesta (síntomas, evidencia,
            citas y tiempos). None si el agente no fue consultado o no aplica.
    """

    role: Role
    content: str
    thread_id: str | None = None
    created_at: datetime | None = None
    trace: ReplyTrace | None = None


@dataclass(frozen=True)
class ConversationThread:
    """Hilo conversacional: un caso o consulta con su resumen.

    Attributes:
        id: Identificador único del hilo.
        domain: Dominio de salud del hilo.
        summary: Resumen de lo conversado en el hilo.
        status: Si el hilo sigue abierto o ya se cerró.
        created_at: Momento de creación.
        updated_at: Momento de la última modificación.
    """

    id: str
    domain: Domain
    summary: str
    status: ThreadStatus
    created_at: datetime
    updated_at: datetime

    @property
    def is_open(self) -> bool:
        """Indica si el hilo sigue abierto."""
        return self.status is ThreadStatus.OPEN


def open_thread(thread_id: str, domain: Domain, summary: str, now: datetime) -> ConversationThread:
    """Crea un hilo nuevo en estado abierto.

    Args:
        thread_id: Identificador único del hilo.
        domain: Dominio de salud inicial.
        summary: Resumen inicial.
        now: Momento de creación.

    Returns:
        El hilo abierto.
    """
    return ConversationThread(thread_id, domain, summary, ThreadStatus.OPEN, now, now)


def update_thread(
    thread: ConversationThread, domain: Domain, summary: str, now: datetime
) -> ConversationThread:
    """Devuelve una copia del hilo con el dominio y el resumen actualizados."""
    return replace(thread, domain=domain, summary=summary, updated_at=now)


def close_thread(thread: ConversationThread, now: datetime) -> ConversationThread:
    """Devuelve una copia del hilo en estado cerrado."""
    return replace(thread, status=ThreadStatus.CLOSED, updated_at=now)
