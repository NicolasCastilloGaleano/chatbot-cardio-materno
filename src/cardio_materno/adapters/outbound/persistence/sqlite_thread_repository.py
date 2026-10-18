"""Repositorio de hilos en SQLite, acotado a un usuario (ADR 0015).

Cada instancia solo ve y modifica los hilos de su dueño (`owner`). Con `owner=None` ve los
hilos sin usuario. Cumple el mismo contrato que
`JsonFileThreadRepository`, así que el agente recibe exactamente el mismo contexto.
"""

import json
import sqlite3
from datetime import datetime

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.trace_codec import (
    trace_from_dict,
    trace_to_dict,
)
from cardio_materno.domain.alarms import Alert, AlertOrigin, Severity
from cardio_materno.domain.conversation import (
    ChatMessage,
    ConversationThread,
    Domain,
    Role,
    ThreadStatus,
)

THREAD_COLUMNS = "id, domain, summary, status, created_at, updated_at"
MESSAGE_COLUMNS = "m.thread_id, m.role, m.content, m.created_at, m.trace_json"
ALERT_COLUMNS = "a.thread_id, a.rule_ids_json, a.severity, a.origin, a.created_at"

UPSERT_THREAD = f"""
    INSERT INTO threads (user_id, {THREAD_COLUMNS}, last_activity_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (id) DO UPDATE SET
        domain = excluded.domain,
        summary = excluded.summary,
        status = excluded.status,
        updated_at = excluded.updated_at,
        last_activity_at = MAX(threads.last_activity_at, excluded.updated_at)
"""
TOUCH_THREAD = "UPDATE threads SET last_activity_at = MAX(last_activity_at, ?) WHERE id = ?"


class SqliteThreadRepository:
    """Implementación de ThreadRepository sobre SQLite para un solo dueño."""

    def __init__(self, database: SqliteDatabase, owner: str | None) -> None:
        """Crea el repositorio acotado.

        Args:
            database: Base SQLite compartida.
            owner: Usuario dueño de los hilos, o None para los hilos sin usuario.
        """
        self._db = database
        self._owner = owner

    def save_thread(self, thread: ConversationThread) -> None:
        """Crea o actualiza el hilo conservando sus mensajes y alertas.

        Raises:
            KeyError: Si el hilo existe y pertenece a otro usuario.
        """
        with self._db.transaction() as connection:
            row = connection.execute(
                "SELECT user_id FROM threads WHERE id = ?", (thread.id,)
            ).fetchone()
            if row is not None and row["user_id"] != self._owner:
                raise KeyError(f"El hilo {thread.id!r} pertenece a otro usuario")
            connection.execute(UPSERT_THREAD, (self._owner, *thread_values(thread)))

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Devuelve el hilo del dueño, o None si no existe o es de otro usuario."""
        rows = self._db.query(
            f"SELECT {THREAD_COLUMNS} FROM threads WHERE id = ? AND user_id IS ?",
            (thread_id, self._owner),
        )
        return thread_from_row(rows[0]) if rows else None

    def list_threads(self) -> list[ConversationThread]:
        """Devuelve los hilos del dueño del más reciente al más antiguo."""
        rows = self._db.query(
            f"SELECT {THREAD_COLUMNS} FROM threads WHERE user_id IS ? ORDER BY updated_at DESC",
            (self._owner,),
        )
        return [thread_from_row(row) for row in rows]

    def all_messages(self, thread_id: str) -> list[ChatMessage]:
        """Devuelve todos los mensajes del hilo en orden (vacío si no es del dueño)."""
        rows = self._db.query(
            f"SELECT {MESSAGE_COLUMNS} FROM messages m JOIN threads t ON t.id = m.thread_id "
            "WHERE m.thread_id = ? AND t.user_id IS ? ORDER BY m.seq",
            (thread_id, self._owner),
        )
        return [message_from_row(row) for row in rows]

    def append_message(self, message: ChatMessage) -> None:
        """Agrega el mensaje a su hilo.

        Raises:
            KeyError: Si el mensaje no tiene hilo o el hilo no es del dueño.
        """
        created_at = message.created_at.isoformat() if message.created_at else None
        trace = (
            json.dumps(trace_to_dict(message.trace), ensure_ascii=False) if message.trace else None
        )
        with self._db.transaction() as connection:
            self._require_thread(connection, message.thread_id)
            connection.execute(
                "INSERT INTO messages (thread_id, role, content, created_at, trace_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (message.thread_id, str(message.role), message.content, created_at, trace),
            )
            if created_at is not None:
                connection.execute(TOUCH_THREAD, (created_at, message.thread_id))

    def append_alert(self, thread_id: str, alert: Alert) -> None:
        """Registra la alerta en el hilo.

        Raises:
            KeyError: Si el hilo no es del dueño.
        """
        with self._db.transaction() as connection:
            self._require_thread(connection, thread_id)
            connection.execute(
                "INSERT INTO alerts (thread_id, rule_ids_json, severity, origin, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    thread_id,
                    json.dumps(list(alert.rule_ids)),
                    str(alert.severity),
                    str(alert.origin),
                    alert.created_at.isoformat(),
                ),
            )

    def all_alerts(self, thread_id: str) -> list[Alert]:
        """Devuelve las alertas del hilo del dueño en orden de registro."""
        rows = self._db.query(
            f"SELECT {ALERT_COLUMNS} FROM alerts a JOIN threads t ON t.id = a.thread_id "
            "WHERE a.thread_id = ? AND t.user_id IS ? ORDER BY a.seq",
            (thread_id, self._owner),
        )
        return [alert_from_row(row) for row in rows]

    def recent_messages(self, thread_id: str, limit: int) -> list[ChatMessage]:
        """Devuelve los últimos `limit` mensajes del hilo, del más antiguo al más reciente."""
        if limit <= 0:
            return []
        rows = self._db.query(
            f"SELECT {MESSAGE_COLUMNS} FROM messages m JOIN threads t ON t.id = m.thread_id "
            "WHERE m.thread_id = ? AND t.user_id IS ? ORDER BY m.seq DESC LIMIT ?",
            (thread_id, self._owner, limit),
        )
        return [message_from_row(row) for row in reversed(rows)]

    def _require_thread(self, connection: sqlite3.Connection, thread_id: str | None) -> None:
        """Verifica que el hilo exista y sea del dueño."""
        row = connection.execute(
            "SELECT 1 FROM threads WHERE id = ? AND user_id IS ?", (thread_id, self._owner)
        ).fetchone()
        if row is None:
            raise KeyError(f"No existe el hilo {thread_id!r}")


def thread_values(thread: ConversationThread) -> tuple[str, ...]:
    """Valores del hilo en el orden de `THREAD_COLUMNS`, más su última actividad."""
    updated_at = thread.updated_at.isoformat()
    return (
        thread.id,
        str(thread.domain),
        thread.summary,
        str(thread.status),
        thread.created_at.isoformat(),
        updated_at,
        updated_at,
    )


def thread_from_row(row: sqlite3.Row) -> ConversationThread:
    """Reconstruye un hilo desde su fila."""
    return ConversationThread(
        id=row["id"],
        domain=Domain(row["domain"]),
        summary=row["summary"],
        status=ThreadStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def message_from_row(row: sqlite3.Row) -> ChatMessage:
    """Reconstruye un mensaje desde su fila."""
    created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    trace = trace_from_dict(json.loads(row["trace_json"])) if row["trace_json"] else None
    return ChatMessage(Role(row["role"]), row["content"], row["thread_id"], created_at, trace)


def alert_from_row(row: sqlite3.Row) -> Alert:
    """Reconstruye una alerta desde su fila."""
    return Alert(
        tuple(json.loads(row["rule_ids_json"])),
        Severity(row["severity"]),
        AlertOrigin(row["origin"]),
        datetime.fromisoformat(row["created_at"]),
    )
