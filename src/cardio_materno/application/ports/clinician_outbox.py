"""Puertos del reenvío por WhatsApp de los mensajes del profesional (HU-16, ADR 0023).

El profesional escribe desde la interfaz web, pero el que envía por WhatsApp es otro proceso.
Por eso el mensaje pasa por una bandeja de salida en la base compartida. El número de la
persona (su `wa_id`) solo se guarda mientras su caso esté abierto y dentro de la ventana; se
borra cuando el caso se cierra o vence y ya no queda nada por enviarle.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class OutboxStatus(StrEnum):
    """Estado de un mensaje de la bandeja de salida."""

    PENDING = "pendiente"
    SENDING = "enviando"
    SENT = "enviado"
    FAILED = "fallido"


@dataclass(frozen=True)
class OutboxItem:
    """Mensaje del profesional pendiente de envío.

    Attributes:
        id: Identificador en la bandeja.
        case_id: Caso al que pertenece.
        user_id: Persona destinataria (seudónimo).
        thread_id: Hilo del caso.
        text: Texto del profesional.
    """

    id: int
    case_id: str
    user_id: str
    thread_id: str
    text: str


class CaseAddressBook(Protocol):
    """Dirección temporal de la persona, del lado del canal (ADR 0023)."""

    def remember(self, case_id: str, user_id: str, reply_to: str, now: datetime) -> None:
        """Guarda o renueva la dirección, solo si el caso está abierto y se le avisó."""
        ...


class ClinicianOutbox(Protocol):
    """Bandeja de salida, del lado del profesional."""

    def reachable(self, case_id: str, now: datetime) -> bool:
        """True si hay una dirección del caso y su ventana sigue abierta."""
        ...

    def enqueue(self, item: OutboxItem, now: datetime) -> None:
        """Deja un mensaje para enviar (el `id` del elemento se ignora)."""
        ...


class OutboxQueue(Protocol):
    """Bandeja de salida, del lado del proceso que envía por WhatsApp."""

    def claim(self, now: datetime) -> list[OutboxItem]:
        """Toma los mensajes pendientes, en orden, y los marca como `enviando`."""
        ...

    def address_of(self, case_id: str) -> str | None:
        """Dirección del caso, o None si ya no hay."""
        ...

    def finish(self, item_id: int, status: OutboxStatus, now: datetime, error: str = "") -> None:
        """Marca el resultado del envío; el texto se borra en ambos casos."""
        ...

    def purge(self, now: datetime) -> int:
        """Falla lo pendiente de casos vencidos y borra las direcciones que ya no hacen falta.

        Returns:
            Cuántas direcciones se borraron.
        """
        ...

    def fail_interrupted(self) -> int:
        """Marca como fallidos los mensajes que quedaron `enviando` tras un reinicio."""
        ...
