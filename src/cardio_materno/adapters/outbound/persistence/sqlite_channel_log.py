"""Registro de mensajes de canal sobre SQLite: deduplicación y auditoría (ADR 0014 y 0015).

No guarda el texto de los mensajes: solo identificadores, tipos, estados y tiempos.
"""

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.application.ports.channel_log import (
    InboundEvent,
    InboundStatus,
    OutboundRecord,
)
from cardio_materno.domain.user import Channel


class SqliteChannelLog:
    """Implementación de ChannelLog sobre SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea el registro.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def register_inbound(self, event: InboundEvent) -> bool:
        """Registra el mensaje; devuelve False si ya estaba (reenvío del canal)."""
        with self._db.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO inbound_events (channel, channel_message_id, user_id, "
                "kind, status, received_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(event.channel),
                    event.channel_message_id,
                    event.user_id,
                    event.kind,
                    str(InboundStatus.RECEIVED),
                    event.received_at.isoformat(),
                ),
            )
            return cursor.rowcount == 1

    def mark_inbound(
        self,
        channel: Channel,
        channel_message_id: str,
        status: InboundStatus,
        error_code: str | None = None,
    ) -> None:
        """Actualiza el estado del mensaje recibido.

        Raises:
            KeyError: Si el mensaje no está registrado.
        """
        with self._db.transaction() as connection:
            cursor = connection.execute(
                "UPDATE inbound_events SET status = ?, error_code = ? "
                "WHERE channel = ? AND channel_message_id = ?",
                (str(status), error_code, str(channel), channel_message_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"No está registrado el mensaje {channel_message_id!r}")

    def fail_unfinished(self, error_code: str) -> int:
        """Marca como fallidos los mensajes recibidos o en proceso; devuelve cuántos."""
        unfinished = (str(InboundStatus.RECEIVED), str(InboundStatus.PROCESSING))
        with self._db.transaction() as connection:
            cursor = connection.execute(
                "UPDATE inbound_events SET status = ?, error_code = ? WHERE status IN (?, ?)",
                (str(InboundStatus.FAILED), error_code, *unfinished),
            )
            return cursor.rowcount

    def record_outbound(self, record: OutboundRecord) -> None:
        """Registra un mensaje enviado."""
        with self._db.transaction() as connection:
            connection.execute(
                "INSERT INTO outbound_messages (channel, user_id, thread_id, kind, "
                "channel_message_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(record.channel),
                    record.user_id,
                    record.thread_id,
                    str(record.kind),
                    record.channel_message_id,
                    record.created_at.isoformat(),
                ),
            )
