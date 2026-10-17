"""Puerto de hilos por usuario (ADR 0015).

Entrega a cada usuario un `ThreadRepository` que solo ve sus hilos. Así el agente recibe
el mismo contexto que en la consola, sin posibilidad de mezclar personas.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.domain.conversation import ConversationThread


@dataclass(frozen=True)
class ActiveThread:
    """Hilo abierto de un usuario y su última actividad.

    Attributes:
        thread: El hilo abierto.
        last_activity: Último mensaje o cambio del hilo (para el cierre por inactividad).
    """

    thread: ConversationThread
    last_activity: datetime


class UserThreadStore(Protocol):
    """Acceso a los hilos de cada usuario."""

    def open_thread(self, user_id: str) -> ActiveThread | None:
        """Devuelve el hilo abierto del usuario (como máximo hay uno), o None."""
        ...

    def scoped(self, user_id: str) -> ThreadRepository:
        """Repositorio que solo lee y escribe los hilos de ese usuario."""
        ...
