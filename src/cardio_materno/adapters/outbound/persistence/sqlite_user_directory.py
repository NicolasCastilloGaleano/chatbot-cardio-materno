"""Directorio de usuarios sobre SQLite (ADR 0015 y 0016).

Solo guarda el hash de la identidad de canal, nunca el teléfono ni el nombre de perfil.
"""

import sqlite3
from datetime import datetime

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.application.ports.user_directory import ChatOwner
from cardio_materno.domain.user import Channel, ConsentStatus, User

USER_COLUMNS = "u.id, u.created_at, u.last_seen_at, u.consent_status, u.live_session_at"


class SqliteUserDirectory:
    """Implementación de UserDirectory sobre SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea el directorio.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def find(self, channel: Channel, user_hash: str) -> User | None:
        """Busca al usuario de una identidad de canal."""
        rows = self._db.query(
            f"SELECT {USER_COLUMNS} FROM channel_identities c JOIN users u ON u.id = c.user_id "
            "WHERE c.channel = ? AND c.channel_user_hash = ?",
            (str(channel), user_hash),
        )
        return user_from_row(rows[0]) if rows else None

    def get(self, user_id: str) -> ChatOwner | None:
        """Devuelve el usuario con el canal de su chat, o None si no existe."""
        rows = self._db.query(
            f"SELECT {USER_COLUMNS}, c.channel FROM users u "
            "JOIN channel_identities c ON c.user_id = u.id WHERE u.id = ? "
            "ORDER BY c.created_at LIMIT 1",
            (user_id,),
        )
        if not rows:
            return None
        return ChatOwner(user_from_row(rows[0]), Channel(rows[0]["channel"]))

    def register(self, user: User, channel: Channel, user_hash: str) -> None:
        """Crea el usuario y su identidad de canal en una sola transacción.

        Raises:
            ValueError: Si la identidad o el usuario ya existen.
        """
        try:
            with self._db.transaction() as connection:
                connection.execute(
                    "INSERT INTO users (id, created_at, last_seen_at, consent_status, "
                    "live_session_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        user.id,
                        *_mutable_values(user),
                    ),
                )
                connection.execute(
                    "INSERT INTO channel_identities (channel, channel_user_hash, user_id, "
                    "created_at) VALUES (?, ?, ?, ?)",
                    (str(channel), user_hash, user.id, user.created_at.isoformat()),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("La identidad de canal ya está registrada") from error

    def save(self, user: User) -> None:
        """Actualiza el último contacto, el consentimiento y el uso en consola.

        Raises:
            KeyError: Si el usuario no existe.
        """
        with self._db.transaction() as connection:
            cursor = connection.execute(
                "UPDATE users SET created_at = ?, last_seen_at = ?, consent_status = ?, "
                "live_session_at = ? WHERE id = ?",
                (*_mutable_values(user), user.id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"No existe el usuario {user.id!r}")


def _mutable_values(user: User) -> tuple[str | None, ...]:
    """Valores del usuario en el orden: creación, último contacto, consentimiento, consola."""
    live = user.live_session_at.isoformat() if user.live_session_at else None
    return (
        user.created_at.isoformat(),
        user.last_seen_at.isoformat(),
        str(user.consent_status),
        live,
    )


def user_from_row(row: sqlite3.Row) -> User:
    """Reconstruye un usuario desde su fila."""
    live = row["live_session_at"]
    return User(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        consent_status=ConsentStatus(row["consent_status"]),
        live_session_at=datetime.fromisoformat(live) if live else None,
    )
