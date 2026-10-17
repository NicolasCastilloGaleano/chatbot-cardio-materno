"""Hilos por usuario sobre SQLite: hilo abierto y repositorio acotado (ADR 0015)."""

from datetime import datetime

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    THREAD_COLUMNS,
    SqliteThreadRepository,
    thread_from_row,
)
from cardio_materno.application.ports.user_thread_store import ActiveThread
from cardio_materno.domain.conversation import ThreadStatus


class SqliteUserThreadStore:
    """Implementación de UserThreadStore sobre SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea el almacén.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def open_thread(self, user_id: str) -> ActiveThread | None:
        """Devuelve el hilo abierto del usuario con su última actividad, o None."""
        rows = self._db.query(
            f"SELECT {THREAD_COLUMNS}, last_activity_at FROM threads "
            "WHERE user_id = ? AND status = ?",
            (user_id, str(ThreadStatus.OPEN)),
        )
        if not rows:
            return None
        last_activity = datetime.fromisoformat(rows[0]["last_activity_at"])
        return ActiveThread(thread_from_row(rows[0]), last_activity)

    def scoped(self, user_id: str) -> SqliteThreadRepository:
        """Repositorio que solo lee y escribe los hilos de ese usuario."""
        return SqliteThreadRepository(self._db, user_id)
