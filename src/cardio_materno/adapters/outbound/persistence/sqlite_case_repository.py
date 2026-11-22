"""Casos escalados a un profesional sobre SQLite (HU-16, ADR 0022).

El resumen clínico se guarda como JSON: no tiene datos de identificación, solo lo que ya
guarda la traza. Un índice único impide dos casos abiertos de la misma persona.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.escalation import (
    OPEN_STATUSES,
    CaseSnapshot,
    CaseStatus,
    ClinicalCase,
)

CASE_COLUMNS = (
    "id, thread_id, status, notified, gap_count, snapshot_json, created_at, expires_at, closed_at"
)
UPSERT_CASE = f"""
    INSERT INTO clinical_cases (user_id, {CASE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET status = excluded.status, gap_count = excluded.gap_count,
        snapshot_json = excluded.snapshot_json, expires_at = excluded.expires_at,
        closed_at = excluded.closed_at
    WHERE clinical_cases.user_id = excluded.user_id
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
        """Crea o actualiza un caso de la persona (no toca casos de otra)."""
        with self._db.transaction() as connection:
            connection.execute(UPSERT_CASE, (self._user_id, *case_values(case)))


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
