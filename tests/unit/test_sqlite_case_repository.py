"""Pruebas de los casos escalados sobre SQLite (HU-16, ADR 0022)."""

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_case_repository import (
    SqliteCaseInbox,
    SqliteCaseStore,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    IN_MEMORY,
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_V3,
    SCHEMA_V4,
    SCHEMA_V5,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.domain.conversation import Domain, open_thread
from cardio_materno.domain.escalation import (
    CaseAction,
    CaseSnapshot,
    CaseStatus,
    ClinicalCase,
    DraftStatus,
    apply_action,
    open_case,
)
from cardio_materno.domain.user import Channel, new_user

NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
WINDOW = timedelta(hours=24)
SNAPSHOT = CaseSnapshot(
    Domain.MATERNAL_CHILD,
    "Ardor.",
    ("ardor",),
    ("FIEBRE",),
    "ardor",
    "sin información",
    "Acidez",
    0.5,
)


@pytest.fixture
def database() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(IN_MEMORY)
    directory = SqliteUserDirectory(db)
    threads = SqliteUserThreadStore(db)
    for user in ("ana", "beto"):
        directory.register(new_user(user, NOW), Channel.WEB, f"hash-{user}")
        threads.scoped(user).save_thread(open_thread(f"t-{user}", Domain.CARDIOVASCULAR, "", NOW))
    yield db
    db.close()


def case(case_id: str = "caso-1", thread_id: str = "t-ana") -> ClinicalCase:
    return open_case(case_id, thread_id, SNAPSHOT, NOW, WINDOW)


def test_a_case_is_saved_and_read_back(database: SqliteDatabase) -> None:
    ana = SqliteCaseStore(database).scoped("ana")

    ana.save(case())

    assert ana.open_case() == case()


def test_a_person_never_sees_the_case_of_another(database: SqliteDatabase) -> None:
    store = SqliteCaseStore(database)
    store.scoped("ana").save(case())

    assert store.scoped("beto").open_case() is None


def test_updates_are_kept_and_a_closed_case_is_not_open(database: SqliteDatabase) -> None:
    ana = SqliteCaseStore(database).scoped("ana")
    ana.save(case())

    ana.save(replace(case(), gap_count=3))
    assert (current := ana.open_case()) is not None and current.gap_count == 3
    SqliteCaseInbox(database).update_if(
        apply_action(current, CaseAction.APPROVE, NOW), current.status
    )

    assert ana.open_case() is None


def test_a_stale_turn_never_reverts_what_the_clinician_did(database: SqliteDatabase) -> None:
    ana, inbox = SqliteCaseStore(database).scoped("ana"), SqliteCaseInbox(database)
    ana.save(case())
    drafted = replace(case(), draft="Borrador.", draft_status=DraftStatus.READY)
    inbox.update_if(drafted, CaseStatus.PENDING)

    ana.save(replace(case(), gap_count=2))
    inbox.update_if(apply_action(drafted, CaseAction.START_CONTACT, NOW), CaseStatus.PENDING)
    ana.save(replace(case(), gap_count=5))

    current = ana.open_case()
    assert current is not None and current.status is CaseStatus.IN_CONTACT
    assert (current.gap_count, current.draft) == (2, "Borrador.")


def test_only_one_open_case_per_person(database: SqliteDatabase) -> None:
    ana = SqliteCaseStore(database).scoped("ana")
    ana.save(case())

    with pytest.raises(sqlite3.IntegrityError):
        ana.save(case("caso-2"))


def test_a_new_case_after_closing_the_previous_one(database: SqliteDatabase) -> None:
    ana = SqliteCaseStore(database).scoped("ana")
    ana.save(apply_action(case(), CaseAction.APPROVE, NOW))

    ana.save(case("caso-2"))

    assert (current := ana.open_case()) is not None and current.id == "caso-2"


def test_version_2_database_gets_the_cases_table(tmp_path: Path) -> None:
    path = tmp_path / "v2.db"
    connection = sqlite3.connect(path)
    for statement in (*SCHEMA_V1, *SCHEMA_V2):
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()

    database = SqliteDatabase(path)
    tables = {row["name"] for row in database.query("SELECT name FROM sqlite_master")}
    database.close()

    assert "clinical_cases" in tables


def test_version_5_database_gets_an_empty_note_on_existing_cases(tmp_path: Path) -> None:
    path = tmp_path / "v5.db"
    connection = sqlite3.connect(path)
    for statement in (*SCHEMA_V1, *SCHEMA_V2, *SCHEMA_V3, *SCHEMA_V4, *SCHEMA_V5):
        connection.execute(statement)
    connection.execute("PRAGMA user_version = 5")
    connection.commit()
    connection.close()
    database = SqliteDatabase(path)
    SqliteUserDirectory(database).register(new_user("ana", NOW), Channel.WEB, "hash-ana")
    thread = open_thread("t-ana", Domain.CARDIOVASCULAR, "", NOW)
    SqliteUserThreadStore(database).scoped("ana").save_thread(thread)
    SqliteCaseStore(database).scoped("ana").save(case("caso-1"))

    rows = database.query("SELECT draft_note FROM clinical_cases")
    database.close()

    assert [row["draft_note"] for row in rows] == [""]
