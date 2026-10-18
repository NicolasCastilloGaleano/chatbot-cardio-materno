"""Conexión y esquema de la base SQLite (ADR 0015).

Un solo archivo (`DATABASE_PATH`) con usuarios, identidades de canal, hilos, mensajes,
alertas y el registro de mensajes de canal. El esquema se versiona con `PRAGMA user_version`.

La conexión se comparte entre hilos del proceso y se protege con un candado: el canal de
WhatsApp procesa con un solo trabajador (ADR 0014), así que no hay contención real.
"""

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cardio_materno.domain.conversation import ThreadStatus

IN_MEMORY = ":memory:"
SCHEMA_VERSION = 1
BUSY_TIMEOUT_MS = 5000

SCHEMA_V1: tuple[str, ...] = (
    """CREATE TABLE users (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        consent_status TEXT NOT NULL,
        consent_at TEXT
    )""",
    """CREATE TABLE channel_identities (
        channel TEXT NOT NULL,
        channel_user_hash TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id),
        created_at TEXT NOT NULL,
        PRIMARY KEY (channel, channel_user_hash)
    )""",
    """CREATE TABLE threads (
        id TEXT PRIMARY KEY,
        user_id TEXT REFERENCES users(id),
        domain TEXT NOT NULL,
        summary TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_activity_at TEXT NOT NULL
    )""",
    "CREATE INDEX threads_by_user ON threads (user_id, updated_at)",
    "CREATE UNIQUE INDEX one_open_thread_per_user ON threads (user_id) "
    f"WHERE status = '{ThreadStatus.OPEN}' AND user_id IS NOT NULL",
    """CREATE TABLE messages (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL REFERENCES threads(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT,
        trace_json TEXT
    )""",
    "CREATE INDEX messages_by_thread ON messages (thread_id, seq)",
    """CREATE TABLE alerts (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL REFERENCES threads(id),
        rule_ids_json TEXT NOT NULL,
        severity TEXT NOT NULL,
        origin TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE inbound_events (
        channel TEXT NOT NULL,
        channel_message_id TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id),
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        error_code TEXT,
        received_at TEXT NOT NULL,
        PRIMARY KEY (channel, channel_message_id)
    )""",
    """CREATE TABLE outbound_messages (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id),
        thread_id TEXT REFERENCES threads(id),
        kind TEXT NOT NULL,
        channel_message_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
)


class DatabaseVersionError(RuntimeError):
    """La base de datos tiene un esquema más nuevo que el que conoce esta versión."""


class SqliteDatabase:
    """Conexión SQLite con transacciones explícitas y esquema versionado."""

    def __init__(self, path: Path | str) -> None:
        """Abre (o crea) la base y aplica el esquema pendiente.

        Args:
            path: Archivo de la base, o ":memory:" para pruebas.

        Raises:
            DatabaseVersionError: Si el archivo tiene un esquema más nuevo.
        """
        self._lock = threading.RLock()
        self._connection = _connect(path)
        self._migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Ejecuta un bloque de escrituras de forma atómica (todo o nada).

        Yields:
            La conexión, dentro de una transacción abierta.
        """
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Ejecuta una consulta de lectura.

        Args:
            sql: Consulta con parámetros `?`.
            params: Valores de los parámetros.

        Returns:
            Las filas resultantes.
        """
        with self._lock:
            return self._connection.execute(sql, params).fetchall()

    def close(self) -> None:
        """Cierra la conexión."""
        with self._lock:
            self._connection.close()

    def _migrate(self) -> None:
        """Crea las tablas si la base es nueva; rechaza esquemas desconocidos."""
        version = int(self.query("PRAGMA user_version")[0][0])
        if version > SCHEMA_VERSION:
            raise DatabaseVersionError(
                f"La base tiene el esquema {version} y esta versión solo conoce hasta "
                f"el {SCHEMA_VERSION}."
            )
        if version == 0:
            with self.transaction() as connection:
                for statement in SCHEMA_V1:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _connect(path: Path | str) -> sqlite3.Connection:
    """Abre la conexión con claves foráneas y, en archivo, modo WAL."""
    if str(path) != IN_MEMORY:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    if str(path) != IN_MEMORY:
        connection.execute("PRAGMA journal_mode = WAL")
    return connection
