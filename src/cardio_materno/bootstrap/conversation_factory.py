"""Servicio conversacional por usuario sobre SQLite, común a todos los canales (ADR 0015 y 0016)."""

import os
from dataclasses import replace
from datetime import timedelta

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    SqliteThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.conversation_service import ConversationService
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.user_conversations import ServiceFactory, UserConversations
from cardio_materno.bootstrap.main import PROJECT_ROOT, build_conversation
from cardio_materno.bootstrap.settings import load_conversation_settings
from cardio_materno.domain.consent import authorizes_research


def build_user_conversations(
    database: SqliteDatabase, idle_timeout: timedelta
) -> UserConversations:
    """Conecta modelos y RAG una sola vez y arma el servicio por usuario.

    Args:
        database: Base SQLite abierta.
        idle_timeout: Inactividad tras la cual se cierra el hilo abierto.

    Returns:
        El componente que crea el servicio de cada usuario con su hilo abierto.
    """
    users = SqliteUserDirectory(database)

    def research_authorized(user_id: str) -> bool:
        owner = users.get(user_id)
        return owner is not None and authorizes_research(owner.user)

    return UserConversations(
        SqliteUserThreadStore(database),
        service_factory(database),
        idle_timeout,
        research_authorized=research_authorized,
    )


def service_factory(database: SqliteDatabase) -> ServiceFactory:
    """Fábrica de servicios: mismos modelos, prompts y RAG; repositorio acotado por usuario."""
    settings = load_conversation_settings(os.environ, PROJECT_ROOT)
    base_ports, config = build_conversation(settings, SqliteThreadRepository(database, None))

    def create(
        repository: ThreadRepository, active_thread_id: str | None, keep_access_facts: bool
    ) -> ConversationService:
        ports = replace(base_ports, repository=repository)
        return ConversationService(ports, config, active_thread_id, keep_access_facts)

    return create
