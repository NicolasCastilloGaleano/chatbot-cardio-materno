"""Direcciones temporales y bandeja de salida del profesional sobre SQLite (HU-16, ADR 0023).

La dirección (`wa_id`) se guarda solo para un caso abierto del que la persona recibió el aviso,
y se borra cuando el caso se cierra o vence y no le queda nada pendiente. El texto de cada
mensaje se borra de la bandeja apenas se envía o falla: ya está en el hilo de la persona.
"""

from datetime import datetime

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.application.ports.clinician_outbox import OutboxItem, OutboxStatus
from cardio_materno.domain.escalation import OPEN_STATUSES

ERROR_WINDOW = "ventana_cerrada"
ERROR_INTERRUPTED = "interrumpido"
OPEN_LIST = ", ".join(f"'{status}'" for status in sorted(OPEN_STATUSES))

REMEMBER = f"""
    INSERT INTO case_addresses (case_id, user_id, reply_to, updated_at)
    SELECT id, user_id, ?, ? FROM clinical_cases
    WHERE id = ? AND user_id = ? AND notified = 1 AND status IN ({OPEN_LIST})
    ON CONFLICT(case_id) DO UPDATE SET reply_to = excluded.reply_to,
        updated_at = excluded.updated_at
"""
REACHABLE = """
    SELECT 1 FROM case_addresses a JOIN clinical_cases c ON c.id = a.case_id
    WHERE a.case_id = ? AND c.expires_at > ?
"""
FAIL_EXPIRED = f"""
    UPDATE clinician_outbox SET status = '{OutboxStatus.FAILED}', error_code = ?, text = '',
        finished_at = ?
    WHERE status = '{OutboxStatus.PENDING}'
        AND case_id IN (SELECT id FROM clinical_cases WHERE expires_at <= ?)
"""
PURGE_ADDRESSES = f"""
    DELETE FROM case_addresses WHERE case_id IN (
        SELECT id FROM clinical_cases
        WHERE status NOT IN ({OPEN_LIST}) OR expires_at <= ?)
    AND case_id NOT IN (
        SELECT case_id FROM clinician_outbox
        WHERE status IN ('{OutboxStatus.PENDING}', '{OutboxStatus.SENDING}'))
"""


class SqliteClinicianOutbox:
    """Implementa `CaseAddressBook`, `ClinicianOutbox` y `OutboxQueue` sobre la base compartida."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea la bandeja.

        Args:
            database: Base SQLite abierta (esquema v4 o posterior).
        """
        self._db = database

    def remember(self, case_id: str, user_id: str, reply_to: str, now: datetime) -> None:
        """Guarda o renueva la dirección, solo si el caso está abierto y se le avisó."""
        with self._db.transaction() as connection:
            connection.execute(REMEMBER, (reply_to, now.isoformat(), case_id, user_id))

    def reachable(self, case_id: str, now: datetime) -> bool:
        """True si hay una dirección del caso y su ventana sigue abierta."""
        return bool(self._db.query(REACHABLE, (case_id, now.isoformat())))

    def enqueue(self, item: OutboxItem, now: datetime) -> None:
        """Deja un mensaje para enviar."""
        with self._db.transaction() as connection:
            connection.execute(
                "INSERT INTO clinician_outbox (case_id, user_id, thread_id, text, status, "
                "error_code, created_at) VALUES (?, ?, ?, ?, ?, '', ?)",
                (
                    item.case_id,
                    item.user_id,
                    item.thread_id,
                    item.text,
                    str(OutboxStatus.PENDING),
                    now.isoformat(),
                ),
            )

    def claim(self, now: datetime) -> list[OutboxItem]:
        """Toma los mensajes pendientes, en orden, y los marca como `enviando`."""
        with self._db.transaction() as connection:
            rows = connection.execute(
                "SELECT id, case_id, user_id, thread_id, text FROM clinician_outbox "
                "WHERE status = ? ORDER BY id",
                (str(OutboxStatus.PENDING),),
            ).fetchall()
            connection.executemany(
                "UPDATE clinician_outbox SET status = ? WHERE id = ?",
                [(str(OutboxStatus.SENDING), row["id"]) for row in rows],
            )
        return [
            OutboxItem(row["id"], row["case_id"], row["user_id"], row["thread_id"], row["text"])
            for row in rows
        ]

    def address_of(self, case_id: str) -> str | None:
        """Dirección del caso, o None si ya no hay."""
        rows = self._db.query("SELECT reply_to FROM case_addresses WHERE case_id = ?", (case_id,))
        return str(rows[0]["reply_to"]) if rows else None

    def finish(self, item_id: int, status: OutboxStatus, now: datetime, error: str = "") -> None:
        """Marca el resultado del envío y borra el texto."""
        with self._db.transaction() as connection:
            connection.execute(
                "UPDATE clinician_outbox SET status = ?, error_code = ?, text = '', "
                "finished_at = ? WHERE id = ?",
                (str(status), error, now.isoformat(), item_id),
            )

    def purge(self, now: datetime) -> int:
        """Falla lo pendiente de casos vencidos y borra las direcciones que ya no hacen falta."""
        stamp = now.isoformat()
        with self._db.transaction() as connection:
            connection.execute(FAIL_EXPIRED, (ERROR_WINDOW, stamp, stamp))
            return connection.execute(PURGE_ADDRESSES, (stamp,)).rowcount

    def fail_interrupted(self) -> int:
        """Marca como fallidos los mensajes que quedaron `enviando` tras un reinicio."""
        with self._db.transaction() as connection:
            return connection.execute(
                "UPDATE clinician_outbox SET status = ?, error_code = ?, text = '' "
                "WHERE status = ?",
                (str(OutboxStatus.FAILED), ERROR_INTERRUPTED, str(OutboxStatus.SENDING)),
            ).rowcount
