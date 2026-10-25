"""Lectura de chats para la auditoría sobre SQLite (HU-10, ADR 0016).

Las páginas usan *keyset* sobre `messages.seq`: no repiten ni saltan mensajes aunque lleguen
mensajes nuevos mientras se audita.
"""

import sqlite3
from collections.abc import Iterable
from datetime import datetime

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    ALERT_COLUMNS,
    alert_from_row,
    message_from_row,
)
from cardio_materno.application.ports.channel_log import InboundStatus
from cardio_materno.application.ports.chat_audit import ChatEntry, ChatPage, ChatSummary
from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import (
    ConversationThread,
    Domain,
    Role,
    ThreadStatus,
)
from cardio_materno.domain.user import Channel

CHAT_SELECT = f"""
    SELECT u.id, u.created_at, u.last_seen_at, u.live_session_at, c.channel,
        (SELECT COUNT(*) FROM messages m JOIN threads t ON t.id = m.thread_id
         WHERE t.user_id = u.id) AS message_count,
        EXISTS (SELECT 1 FROM threads t WHERE t.user_id = u.id
                AND t.status = '{ThreadStatus.OPEN}') AS has_open_thread
    FROM users u JOIN channel_identities c ON c.user_id = u.id
"""
ENTRY_SELECT = """
    SELECT m.seq, m.thread_id, m.role, m.content, m.created_at, m.trace_json,
        t.domain AS t_domain, t.summary AS t_summary, t.status AS t_status,
        t.created_at AS t_created_at, t.updated_at AS t_updated_at
    FROM messages m JOIN threads t ON t.id = m.thread_id
"""
UNFINISHED = (str(InboundStatus.RECEIVED), str(InboundStatus.PROCESSING))

AlertKey = tuple[str, str]


class SqliteChatAudit:
    """Implementación de ChatAudit sobre SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea el lector.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def list_chats(self, channel: Channel | None, limit: int, offset: int) -> list[ChatSummary]:
        """Chats del más reciente al más antiguo, opcionalmente de un solo canal."""
        value = str(channel) if channel else None
        rows = self._db.query(
            f"{CHAT_SELECT} WHERE (? IS NULL OR c.channel = ?) "
            "ORDER BY u.last_seen_at DESC, u.id LIMIT ? OFFSET ?",
            (value, value, limit, offset),
        )
        return [summary_from_row(row) for row in rows]

    def get_chat(self, user_id: str) -> ChatSummary | None:
        """Resumen de un chat, o None si no existe."""
        rows = self._db.query(f"{CHAT_SELECT} WHERE u.id = ? LIMIT 1", (user_id,))
        return summary_from_row(rows[0]) if rows else None

    def message_page(self, user_id: str, before: int | None, limit: int) -> ChatPage:
        """Los `limit` mensajes anteriores a `before` (o los más recientes si es None)."""
        rows = self._db.query(
            f"{ENTRY_SELECT} WHERE t.user_id = ? AND (? IS NULL OR m.seq < ?) "
            "ORDER BY m.seq DESC LIMIT ?",
            (user_id, before, before, limit + 1),
        )
        page = list(reversed(rows[:limit]))
        next_before = int(page[0]["seq"]) if len(rows) > limit and page else None
        return ChatPage(self._entries(page), next_before)

    def messages_after(self, user_id: str, after: int, limit: int) -> ChatPage:
        """Hasta `limit` mensajes posteriores a `after`, en orden cronológico."""
        rows = self._db.query(
            f"{ENTRY_SELECT} WHERE t.user_id = ? AND m.seq > ? ORDER BY m.seq LIMIT ?",
            (user_id, after, limit),
        )
        return ChatPage(self._entries(rows))

    def pending_inbound(self, user_id: str) -> int:
        """Mensajes del canal recibidos y aún en proceso."""
        rows = self._db.query(
            "SELECT COUNT(*) FROM inbound_events WHERE user_id = ? AND status IN (?, ?)",
            (user_id, *UNFINISHED),
        )
        return int(rows[0][0])

    def _entries(self, rows: list[sqlite3.Row]) -> tuple[ChatEntry, ...]:
        """Convierte las filas en entradas y adjunta las alertas a cada respuesta."""
        alerts = self._alerts_by_turn({row["thread_id"] for row in rows})
        return tuple(entry_from_row(row, alerts) for row in rows)

    def _alerts_by_turn(self, thread_ids: Iterable[str]) -> dict[AlertKey, tuple[Alert, ...]]:
        """Alertas de los hilos, agrupadas por (hilo, momento del turno)."""
        ids = list(thread_ids)
        if not ids:
            return {}
        marks = ", ".join("?" for _ in ids)
        rows = self._db.query(
            f"SELECT {ALERT_COLUMNS} FROM alerts a WHERE a.thread_id IN ({marks}) ORDER BY a.seq",
            ids,
        )
        grouped: dict[AlertKey, tuple[Alert, ...]] = {}
        for row in rows:
            key = (row["thread_id"], row["created_at"])
            grouped[key] = (*grouped.get(key, ()), alert_from_row(row))
        return grouped


def summary_from_row(row: sqlite3.Row) -> ChatSummary:
    """Reconstruye el resumen de un chat."""
    live = row["live_session_at"]
    return ChatSummary(
        user_id=row["id"],
        channel=Channel(row["channel"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        message_count=int(row["message_count"]),
        has_open_thread=bool(row["has_open_thread"]),
        live_session_at=datetime.fromisoformat(live) if live else None,
    )


def entry_from_row(row: sqlite3.Row, alerts: dict[AlertKey, tuple[Alert, ...]]) -> ChatEntry:
    """Reconstruye un mensaje con su hilo; las respuestas llevan las alertas de su turno."""
    message = message_from_row(row)
    turn_alerts = (
        alerts.get((row["thread_id"], row["created_at"]), ())
        if message.role is Role.ASSISTANT
        else ()
    )
    return ChatEntry(int(row["seq"]), message, thread_from_entry_row(row), turn_alerts)


def thread_from_entry_row(row: sqlite3.Row) -> ConversationThread:
    """Hilo de una fila de mensaje (columnas con prefijo `t_`)."""
    return ConversationThread(
        id=row["thread_id"],
        domain=Domain(row["t_domain"]),
        summary=row["t_summary"],
        status=ThreadStatus(row["t_status"]),
        created_at=datetime.fromisoformat(row["t_created_at"]),
        updated_at=datetime.fromisoformat(row["t_updated_at"]),
    )
