"""Casos escalados a un profesional sobre SQLite (HU-16, ADR 0022).

El resumen clínico se guarda como JSON: no tiene datos de identificación, solo lo que ya
guarda la traza. Un índice único impide dos casos abiertos de la misma persona.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.application.ports.case_inbox import InboxCase
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.escalation import (
    OPEN_STATUSES,
    CaseSnapshot,
    CaseStatus,
    ClinicalCase,
    DraftStatus,
)
from cardio_materno.domain.user import Channel

CASE_COLUMNS = (
    "id, thread_id, status, notified, gap_count, snapshot_json, created_at, expires_at, "
    "closed_at, draft_text, draft_status, draft_note"
)
# Del lado de la persona solo cambian el aviso, las brechas, el resumen y el vencimiento. El
# estado y el borrador son del profesional (`update_if`): un turno que leyó el caso antes de que
# el profesional actuara no los revierte, y si el estado ya cambió, no se toca nada.
UPSERT_CASE = f"""
    INSERT INTO clinical_cases (user_id, {CASE_COLUMNS})
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET notified = excluded.notified,
        gap_count = excluded.gap_count,
        snapshot_json = excluded.snapshot_json, expires_at = excluded.expires_at
    WHERE clinical_cases.user_id = excluded.user_id
        AND clinical_cases.status = excluded.status
"""

# La bandeja lee el canal del chat de la persona para saber cómo entregar la respuesta.
INBOX_SELECT = f"""
    SELECT user_id, {CASE_COLUMNS},
        (SELECT channel FROM channel_identities ci WHERE ci.user_id = clinical_cases.user_id
         LIMIT 1) AS channel
    FROM clinical_cases
"""
# El profesional solo cambia el estado y el borrador: las brechas, el resumen y el vencimiento
# son del lado de la persona (`UPSERT_CASE`), así ninguno revierte lo que escribió el otro.
UPDATE_IF_STATUS = """
    UPDATE clinical_cases SET status = ?, closed_at = ?, draft_text = ?, draft_status = ?,
        draft_note = ?
    WHERE id = ? AND status = ?
"""


class SqliteCaseStore:
    """Implementación de CaseStore sobre SQLite."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea el almacén.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def scoped(self, user_id: str) -> "SqliteCaseRepository":
        """Repositorio que solo lee y escribe los casos de esa persona."""
        return SqliteCaseRepository(self._db, user_id)


class SqliteCaseRepository:
    """Implementación de CaseRepository acotada a una persona."""

    def __init__(self, database: SqliteDatabase, user_id: str) -> None:
        """Crea el repositorio.

        Args:
            database: Base SQLite compartida.
            user_id: Persona dueña de los casos.
        """
        self._db = database
        self._user_id = user_id

    def open_case(self) -> ClinicalCase | None:
        """Devuelve el caso abierto de la persona, o None."""
        marks = ", ".join("?" for _ in OPEN_STATUSES)
        rows = self._db.query(
            f"SELECT {CASE_COLUMNS} FROM clinical_cases WHERE user_id = ? AND status IN ({marks})",
            (self._user_id, *(str(status) for status in OPEN_STATUSES)),
        )
        return case_from_row(rows[0]) if rows else None

    def save(self, case: ClinicalCase) -> None:
        """Crea un caso o actualiza lo que cambia del lado de la persona (no toca casos de otra).

        El estado y el borrador solo los cambia el profesional, con `CaseInbox.update_if`.
        """
        with self._db.transaction() as connection:
            connection.execute(UPSERT_CASE, (self._user_id, *case_values(case)))


class SqliteCaseInbox:
    """Implementación de CaseInbox sobre SQLite: los casos de todas las personas."""

    def __init__(self, database: SqliteDatabase) -> None:
        """Crea la bandeja.

        Args:
            database: Base SQLite compartida.
        """
        self._db = database

    def list_open(self) -> list[InboxCase]:
        """Casos abiertos con aviso a la persona, del más antiguo al más nuevo."""
        marks = ", ".join("?" for _ in OPEN_STATUSES)
        rows = self._db.query(
            f"{INBOX_SELECT} WHERE status IN ({marks}) AND notified = 1 ORDER BY created_at",
            tuple(str(status) for status in OPEN_STATUSES),
        )
        return [inbox_case_from_row(row) for row in rows]

    def get(self, case_id: str) -> InboxCase | None:
        """Un caso por su id, o None."""
        rows = self._db.query(f"{INBOX_SELECT} WHERE id = ?", (case_id,))
        return inbox_case_from_row(rows[0]) if rows else None

    def update_if(self, case: ClinicalCase, expected: CaseStatus) -> bool:
        """Guarda el estado y el borrador del caso solo si su estado sigue siendo `expected`."""
        values = case_values(case)
        changes = (values[2], *values[8:])
        with self._db.transaction() as connection:
            cursor = connection.execute(UPDATE_IF_STATUS, (*changes, case.id, str(expected)))
        return cursor.rowcount == 1

    def expire_due(self, now: datetime) -> int:
        """Vence los casos abiertos cuyo plazo pasó."""
        marks = ", ".join("?" for _ in OPEN_STATUSES)
        stamp = now.isoformat()
        with self._db.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE clinical_cases SET status = ?, closed_at = ? "
                f"WHERE status IN ({marks}) AND expires_at <= ?",
                (str(CaseStatus.EXPIRED), stamp, *(str(s) for s in OPEN_STATUSES), stamp),
            )
        return cursor.rowcount


def inbox_case_from_row(row: sqlite3.Row) -> InboxCase:
    """Caso de la bandeja con su persona y el canal de su chat."""
    return InboxCase(case_from_row(row), row["user_id"], Channel(row["channel"]))


def case_values(case: ClinicalCase) -> tuple[Any, ...]:
    """Valores de las columnas de `CASE_COLUMNS`, en orden."""
    return (
        case.id,
        case.thread_id,
        str(case.status),
        int(case.notified),
        case.gap_count,
        json.dumps(snapshot_to_dict(case.snapshot), ensure_ascii=False),
        case.created_at.isoformat(),
        case.expires_at.isoformat(),
        case.closed_at.isoformat() if case.closed_at else None,
        case.draft,
        str(case.draft_status),
        case.draft_note,
    )


def case_from_row(row: sqlite3.Row) -> ClinicalCase:
    """Reconstruye un caso desde una fila con `CASE_COLUMNS`."""
    closed = row["closed_at"]
    return ClinicalCase(
        id=row["id"],
        thread_id=row["thread_id"],
        snapshot=snapshot_from_dict(json.loads(row["snapshot_json"])),
        status=CaseStatus(row["status"]),
        notified=bool(row["notified"]),
        gap_count=row["gap_count"],
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        closed_at=datetime.fromisoformat(closed) if closed else None,
        draft=row["draft_text"],
        draft_status=DraftStatus(row["draft_status"]),
        draft_note=row["draft_note"],
    )


def snapshot_to_dict(snapshot: CaseSnapshot) -> dict[str, Any]:
    """Resumen clínico como diccionario serializable."""
    return {
        "domain": str(snapshot.domain),
        "summary": snapshot.summary,
        "symptoms": list(snapshot.symptoms),
        "signs": list(snapshot.signs),
        "query": snapshot.query,
        "reason": snapshot.reason,
        "category": snapshot.category,
        "best_score": snapshot.best_score,
    }


def snapshot_from_dict(data: dict[str, Any]) -> CaseSnapshot:
    """Reconstruye el resumen clínico guardado."""
    return CaseSnapshot(
        domain=Domain(data["domain"]),
        summary=data["summary"],
        symptoms=tuple(data["symptoms"]),
        signs=tuple(data["signs"]),
        query=data["query"],
        reason=data["reason"],
        category=data["category"],
        best_score=float(data["best_score"]),
    )
