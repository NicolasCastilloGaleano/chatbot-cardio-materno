"""Servicio conversacional de cada usuario, compartido por todos los canales (ADR 0015 y 0016).

Cierra el hilo inactivo y crea un `ConversationService` con el repositorio acotado al usuario
y su hilo abierto. Así WhatsApp, la consola y la web aplican la misma regla y el agente
recibe el mismo contexto en todos los canales.
"""

from collections.abc import Callable
from datetime import timedelta

from cardio_materno.application.conversation_service import (
    Clock,
    ConversationService,
    utc_now,
)
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.ports.user_thread_store import UserThreadStore
from cardio_materno.domain.conversation import close_thread
from cardio_materno.domain.user import is_idle

# Repositorio acotado, hilo activo y si se guardan los códigos de acceso (ADR 0023).
ServiceFactory = Callable[[ThreadRepository, str | None, bool], ConversationService]
ResearchCheck = Callable[[str], bool]


def no_research(user_id: str) -> bool:
    """Nadie autorizó el uso en informes: los códigos de acceso no se guardan."""
    return False


class UserConversations:
    """Crea el servicio conversacional de un usuario con su hilo abierto."""

    def __init__(
        self,
        threads: UserThreadStore,
        service_factory: ServiceFactory,
        idle_timeout: timedelta,
        clock: Clock = utc_now,
        research_authorized: ResearchCheck = no_research,
    ) -> None:
        """Crea el componente.

        Args:
            threads: Hilos por usuario.
            service_factory: Crea el servicio para un repositorio acotado y un hilo activo.
            idle_timeout: Inactividad tras la cual se cierra el hilo abierto.
            clock: Reloj (UTC).
            research_authorized: Dice si un usuario autorizó usar sus datos de acceso en
                informes agregados (ADR 0023).
        """
        self._threads = threads
        self._research_authorized = research_authorized
        self._service_factory = service_factory
        self._idle_timeout = idle_timeout
        self._clock = clock

    def service_for(self, user_id: str) -> ConversationService:
        """Servicio con el repositorio del usuario y su hilo abierto (cerrado si está inactivo)."""
        repository = self._threads.scoped(user_id)
        active = self._threads.open_thread(user_id)
        now = self._clock()
        if active is not None and is_idle(active.last_activity, now, self._idle_timeout):
            repository.save_thread(close_thread(active.thread, now))
            active = None
        thread_id = active.thread.id if active else None
        return self._service_factory(repository, thread_id, self._research_authorized(user_id))

    def close_open_thread(self, user_id: str) -> None:
        """Cierra el hilo abierto del usuario, si lo hay (fin de una sesión de consola)."""
        active = self._threads.open_thread(user_id)
        if active is not None:
            self._threads.scoped(user_id).save_thread(close_thread(active.thread, self._clock()))
