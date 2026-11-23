"""Informe agregado, autorización para informes, migración v3 y API (HU-18, ADR 0023)."""

import argparse
import itertools
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from scripts.export_care_access import closed_until, collect, export
from scripts.export_traces import connect_read_only

from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    load_care_access_catalog,
    load_public_emergency_info,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_VERSION,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.care_access import CareAccessActivation
from cardio_materno.application.care_access_report import (
    CONTRADICTORY_STAGE,
    GROUP_CASCADE,
    GROUP_TOTAL,
    Observation,
    ReportPolicy,
    build_report,
    protect,
)
from cardio_materno.domain.care_access import CareAccessCatalog
from cardio_materno.domain.consent import (
    authorizes_research,
    with_consent_decision,
    with_research_decision,
)
from cardio_materno.domain.user import Channel, ConsentStatus, new_user
from tests.unit.fakes import (
    FakeClock,
    ScriptedAgent,
    agent_json,
    citing,
    make_alarm_policy,
    make_user_conversations,
)
from tests.unit.test_citizen_view import say, start
from tests.unit.test_web_app import WebHarness, build, database

__all__ = ["database"]

REPO = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO / "knowledge" / "care_access.json"
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
LATER = datetime(2027, 1, 15, tzinfo=UTC)
POLICY = ReportPolicy()


@pytest.fixture(scope="module")
def catalog() -> CareAccessCatalog:
    return load_care_access_catalog(CATALOG_FILE)


def people(count: int, period: str, *facts: str, start: int = 0) -> list[Observation]:
    return [Observation(f"p{n}", period, facts) for n in range(start, start + count)]


def published(rows: list[Any], indicator: str) -> list[str]:
    return [row.published for row in rows if indicator in row.indicator]


# --- Protección de los conteos ------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "shown"),
    [(0, "<5"), (1, "<5"), (4, "<5"), (5, "5"), (7, "5"), (8, "10"), (12, "10"), (13, "15")],
)
def test_small_counts_are_suppressed_and_the_rest_rounded(count: int, shown: str) -> None:
    assert protect(count, POLICY) == shown


def test_several_threads_of_one_person_count_once(catalog: CareAccessCatalog) -> None:
    same_person = [Observation("p0", "2026-10", ("SIN_AFILIACION",)) for _ in range(30)]
    rows = build_report(
        [*same_person, *people(11, "2026-10", "BARRERA_COSTO", start=1)], catalog, POLICY
    )

    assert published(rows, "personas con datos") == ["10"]
    assert published(rows, "no tiene EPS") == ["<5"]


def test_a_month_with_few_people_is_not_published(catalog: CareAccessCatalog) -> None:
    rows = build_report(people(9, "2026-10", "SIN_AFILIACION"), catalog, POLICY)

    assert len(rows) == 1 and rows[0].group == GROUP_TOTAL
    assert rows[0].published.startswith("omitido")


def test_one_more_person_cannot_be_told_from_the_difference(catalog: CareAccessCatalog) -> None:
    before = build_report(people(11, "2026-10", "SIN_AFILIACION"), catalog, POLICY)
    after = build_report(people(12, "2026-10", "SIN_AFILIACION"), catalog, POLICY)

    assert [row.published for row in before] == [row.published for row in after]


def test_every_indicator_is_listed_so_a_row_never_reveals_that_someone_declared_it(
    catalog: CareAccessCatalog,
) -> None:
    with_one = [
        *people(11, "2026-10", "BARRERA_COSTO"),
        Observation("x", "2026-10", ("SIN_AFILIACION",)),
    ]
    without = people(12, "2026-10", "BARRERA_COSTO")

    one, none = build_report(with_one, catalog, POLICY), build_report(without, catalog, POLICY)

    assert [(r.group, r.indicator) for r in one] == [(r.group, r.indicator) for r in none]
    assert published(one, "no tiene EPS") == published(none, "no tiene EPS") == ["<5"]


@pytest.mark.parametrize(("sharing", "shown"), [(20, "suprimido"), (17, "suprimido"), (15, "15")])
def test_a_fact_shared_by_almost_everyone_is_suppressed(
    catalog: CareAccessCatalog, sharing: int, shown: str
) -> None:
    group = people(sharing, "2026-10", "SIN_AFILIACION")
    rest = people(20 - sharing, "2026-10", "BARRERA_COSTO", start=sharing)

    rows = build_report([*group, *rest], catalog, POLICY)

    assert published(rows, "no tiene EPS") == [shown]


def test_known_limit_a_count_on_the_rounding_edge_moves_when_one_person_leaves(
    catalog: CareAccessCatalog,
) -> None:
    # Límite documentado (ADR 0023): el redondeo no esconde un retiro en el borde. Por eso
    # cada mes cerrado se publica una sola vez. Si esto cambia, hay que revisar esa regla.
    rest = people(20, "2026-10", "BARRERA_COSTO", start=13)
    before = build_report([*people(13, "2026-10", "SIN_AFILIACION"), *rest], catalog, POLICY)
    after = build_report([*people(12, "2026-10", "SIN_AFILIACION"), *rest], catalog, POLICY)

    assert published(before, "no tiene EPS") == ["15"]
    assert published(after, "no tiene EPS") == ["10"]


def test_the_cascade_is_reported_as_declared_never_inferred(catalog: CareAccessCatalog) -> None:
    treated_only = people(12, "2026-10", "TRATAMIENTO_COLESTEROL")
    conflicting = people(12, "2026-11", "COLESTEROL_ALTO", "COLESTEROL_NORMAL")
    others = people(8, "2026-11", "BARRERA_COSTO", start=12)

    rows = build_report([*treated_only, *conflicting, *others], catalog, POLICY)

    october = [row for row in rows if row.period == "2026-10" and row.group == GROUP_CASCADE]
    november = {row.indicator: row.published for row in rows if row.period == "2026-11"}
    assert {row.published for row in october} == {"<5"}
    assert november[CONTRADICTORY_STAGE] == "10"
    assert november["declara colesterol alto sin tratamiento"] == "<5"


# --- Exportación desde la base ------------------------------------------------------------


def seed(path: Path, catalog: CareAccessCatalog, authorized: int, others: int) -> None:
    """Personas sintéticas que dicen no tener EPS; solo algunas autorizan el informe."""
    db = SqliteDatabase(path)
    users, clock, ids = SqliteUserDirectory(db), FakeClock(), itertools.count()
    turn = citing(agent_json("Come más verduras."), "E1") | {"access_facts": ["COLESTEROL_ALTO"]}
    agent = ScriptedAgent(*[turn] * 200)

    def research(user_id: str) -> bool:
        owner = users.get(user_id)
        return owner is not None and authorizes_research(owner.user)

    config = {
        "alarm_policy": make_alarm_policy(),
        "care_access": catalog,
        "care_access_activation": CareAccessActivation.OBSERVE,
        "research_authorized": research,
    }
    conversations = make_user_conversations(
        agent, SqliteUserThreadStore(db), clock, service_config=config
    )
    for number in range(authorized + others):
        user = new_user(f"u{number}", NOW)
        users.register(user, Channel.WEB, f"hash-{next(ids)}")
        if number < authorized:
            users.save(with_research_decision(user, True, NOW))
        conversations.service_for(user.id).send("tengo el colesterol alto y no tengo eps")
    db.close()


def arguments(**options: Any) -> argparse.Namespace:
    return argparse.Namespace(catalog=CATALOG_FILE, since="0000-00", until=None, **options)


def test_only_people_who_authorized_are_counted(tmp_path: Path, catalog: CareAccessCatalog) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=12, others=7)
    connection = connect_read_only(path)

    observations = collect(connection, "0000-00", "2027-01")
    lines = export(connection, arguments(), LATER)
    connection.close()

    assert {observation.person for observation in observations} == {f"u{n}" for n in range(12)}
    assert lines[0].startswith("# No es una estimación representativa de Caldas")
    assert lines[1] == "periodo,grupo,indicador,personas"
    assert "2026-10,total,personas con datos de acceso declarados,10" in lines
    assert any("no tiene EPS" in line and line.endswith(",suprimido") for line in lines)


def test_codes_of_people_who_did_not_authorize_never_reach_the_database(
    tmp_path: Path, catalog: CareAccessCatalog
) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=1, others=3)
    connection = sqlite3.connect(path)

    rows = connection.execute(
        "SELECT t.user_id, m.trace_json FROM messages m JOIN threads t ON t.id = m.thread_id "
        "WHERE m.trace_json IS NOT NULL"
    ).fetchall()
    connection.close()

    with_codes = {user for user, trace in rows if "SIN_AFILIACION" in trace}
    assert with_codes == {"u0"} and len(rows) == 4


def test_the_current_month_is_never_exported(tmp_path: Path, catalog: CareAccessCatalog) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=12, others=0)
    connection = connect_read_only(path)

    same_month = export(connection, arguments(), datetime(2026, 10, 28, tzinfo=UTC))
    repeated = [export(connection, arguments(), LATER) for _ in range(2)]
    connection.close()

    assert same_month[2:] == []
    assert repeated[0] == repeated[1]
    assert (
        closed_until("2030-01", LATER) == "2027-01" and closed_until("2026-11", LATER) == "2026-11"
    )


def test_withdrawing_the_authorization_removes_the_person_from_the_report(
    tmp_path: Path, catalog: CareAccessCatalog
) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=12, others=0)
    db = SqliteDatabase(path)
    users = SqliteUserDirectory(db)
    owner = users.get("u0")
    assert owner is not None
    users.save(with_research_decision(owner.user, False, NOW))
    db.close()
    connection = connect_read_only(path)

    observations = collect(connection, "0000-00", "2027-01")
    connection.close()

    assert "u0" not in {observation.person for observation in observations}


# --- Migración v3 -------------------------------------------------------------------------


def test_refusing_the_consent_also_ends_the_research_use(
    tmp_path: Path, catalog: CareAccessCatalog
) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=12, others=0)
    db = SqliteDatabase(path)
    users = SqliteUserDirectory(db)
    for number in range(3):
        owner = users.get(f"u{number}")
        assert owner is not None
        refused = with_consent_decision(owner.user, False, NOW)
        assert not authorizes_research(refused)
        assert refused.research_consent is ConsentStatus.REJECTED
        users.save(replace(refused, research_consent=ConsentStatus.ACCEPTED))
    db.close()
    connection = connect_read_only(path)

    counted = {observation.person for observation in collect(connection, "0000-00", "2027-01")}
    connection.close()

    assert counted == {f"u{n}" for n in range(3, 12)}


def test_a_closed_month_does_not_receive_later_messages(
    tmp_path: Path, catalog: CareAccessCatalog
) -> None:
    path = tmp_path / "base.db"
    seed(path, catalog, authorized=1, others=0)
    db = SqliteDatabase(path)
    with db.transaction() as connection:
        connection.execute("UPDATE messages SET created_at = '2026-11-01T00:30:00+00:00'")
    db.close()
    connection = connect_read_only(path)

    october = collect(connection, "0000-00", "2026-11")
    november = collect(connection, "2026-11", "2026-12")
    connection.close()

    assert october == []
    assert {observation.period for observation in november} == {"2026-11"}


def test_version_2_database_is_migrated_without_touching_its_data(tmp_path: Path) -> None:
    path = tmp_path / "v2.db"
    connection = sqlite3.connect(path)
    for statement in (*SCHEMA_V1, *SCHEMA_V2):
        connection.execute(statement)
    connection.execute(
        "INSERT INTO users (id, created_at, last_seen_at, consent_status, consent_at) "
        "VALUES ('ana', ?, ?, 'aceptado', ?)",
        (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO channel_identities VALUES ('whatsapp', 'h', 'ana', ?)", (NOW.isoformat(),)
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()

    db = SqliteDatabase(path)
    users = SqliteUserDirectory(db)
    owner = users.get("ana")

    assert db.query("PRAGMA user_version")[0][0] == SCHEMA_VERSION
    assert owner is not None and owner.user.consent_status is ConsentStatus.ACCEPTED
    assert owner.user.consent_at == NOW
    assert owner.user.research_consent is ConsentStatus.PENDING and owner.user.research_at is None
    users.save(with_research_decision(owner.user, True, NOW))
    saved = users.get("ana")
    assert saved is not None and authorizes_research(saved.user) and saved.user.research_at == NOW
    db.close()


# --- API ----------------------------------------------------------------------------------


def with_access(database: SqliteDatabase, *turns: dict[str, Any], **options: Any) -> WebHarness:
    """Interfaz con la regla de acceso y un catálogo aprobado solo para la prueba."""
    return build(database, *turns, care_access=True, **options)


def test_emergency_information_needs_no_session_and_no_consent(database: SqliteDatabase) -> None:
    harness = build(database, consent_required=True)

    response = harness.client.get("/api/public/emergency")

    assert response.status_code == 200 and response.json()["phone"] == "123"
    assert database.query("SELECT COUNT(*) FROM users")[0][0] == 0
    page = harness.client.get("/").text
    assert 'id="emergency-dialog"' in page and 'href="tel:123"' in page


def test_research_authorization_is_separate_from_consent(database: SqliteDatabase) -> None:
    turn = citing(agent_json("Come más verduras."), "E1")
    harness = with_access(database, turn, turn, consent_required=True)
    session = start(harness)
    sid = session["session"]

    harness.client.post(f"/api/me/sessions/{sid}/consent", json={"accepted": True})
    attended = say(harness, sid, "tengo acidez")
    granted = harness.client.post(f"/api/me/sessions/{sid}/research", json={"accepted": True})
    withdrawn = harness.client.post(f"/api/me/sessions/{sid}/research", json={"accepted": False})

    assert session["research"] == "pendiente" and session["research_text"]
    assert attended.status_code == 200
    assert granted.json()["research"] == "aceptado" and granted.json()["consent"] == "aceptado"
    assert withdrawn.json()["research"] == "rechazado"
    assert say(harness, sid, "tengo acidez").status_code == 200


def test_research_is_not_offered_when_the_rule_is_off(database: SqliteDatabase) -> None:
    assert start(build(database))["research_text"] == ""


def test_the_access_notice_is_told_apart_from_the_evidence(database: SqliteDatabase) -> None:
    harness = with_access(database, citing(agent_json("Come más verduras."), "E1"))
    sid = start(harness)["session"]

    turn = say(harness, sid, "tengo el colesterol alto y no tengo eps").json()
    saved = harness.client.get(f"/api/me/sessions/{sid}/messages").json()["messages"][1]

    notice = turn["access_notice"]
    assert notice["kind"] == "administrativo" and notice["text"] in turn["reply"]
    assert notice["basis"] and turn["grounded"] and turn["sources"]
    assert saved["access_notice"] == notice
    assert "stated_facts" not in turn and "care_access" not in turn


def test_the_team_sees_live_codes_but_they_are_not_stored(database: SqliteDatabase) -> None:
    harness = with_access(database, citing(agent_json("Come más verduras."), "E1"))
    chat_id = harness.client.post("/api/chats").json()["id"]

    body = harness.client.post(
        f"/api/chats/{chat_id}/messages", json={"text": "no tengo eps", "after": 0}
    ).json()

    live = body["turn"]["trace"]["care_access"]
    stored = body["messages"][-1]["trace"]["care_access"]
    assert live["stated_facts"][0]["code"] == "SIN_AFILIACION" and live["applied"]
    assert stored["stated_facts"] == [] and stored["facts_withheld"]
    assert load_public_emergency_info(REPO / "knowledge" / "public_info.json").lines
