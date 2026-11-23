"""Vista ciudadana (HU-16), consentimiento en la web (HU-01) y bandeja de alertas (HU-17)."""

from typing import Any

from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.application.errors import LanguageModelError
from tests.unit.fakes import PRIORITY_MESSAGE, URGENT_MESSAGE, agent_json, citing, scoped
from tests.unit.test_web_app import WebHarness, build, database, whatsapp_chat

__all__ = ["database"]

REPLY = "Orientación validada para la prueba"


def start(harness: WebHarness) -> dict[str, Any]:
    response = harness.client.post("/api/me/sessions")
    assert response.status_code == 201
    session: dict[str, Any] = response.json()
    return session


def say(harness: WebHarness, session: str, text: str) -> Any:
    return harness.client.post(f"/api/me/sessions/{session}/messages", json={"text": text})


def history(harness: WebHarness, session: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = harness.client.get(
        f"/api/me/sessions/{session}/messages"
    ).json()["messages"]
    return messages


# --- Conversación propia ----------------------------------------------------------------


def test_a_reply_names_its_sources_and_hides_the_audit_data(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"))
    session = start(harness)["session"]

    turn = say(harness, session, "tengo acidez").json()

    assert turn["reply"] == REPLY and turn["kind"] == "respuesta" and turn["saved"]
    assert turn["grounded"] and turn["sources"][0]["id"] == "OPS-HEARTS"
    saved = history(harness, session)
    assert [message["role"] for message in saved] == ["user", "assistant"]
    assert saved[1]["sources"][0]["url"].startswith("https://")
    assert "trace" not in saved[1] and "thread" not in saved[1] and "trace" not in turn


def test_an_urgency_is_marked_so_the_page_can_highlight_it(database: SqliteDatabase) -> None:
    harness = build(database)
    session = start(harness)["session"]

    turn = say(harness, session, "tengo sangrado vaginal").json()

    assert turn["reply"] == URGENT_MESSAGE and turn["kind"] == "urgencia"
    assert not turn["grounded"] and turn["sources"] == []
    assert history(harness, session)[1]["kind"] == "urgencia"


def test_an_out_of_scope_turn_is_answered_but_not_saved(database: SqliteDatabase) -> None:
    harness = build(database, scoped(agent_json("x"), "fuera_de_alcance"))
    session = start(harness)["session"]

    turn = say(harness, session, "¿quién ganó el partido?").json()

    assert turn["saved"] is False and turn["reply"]
    assert history(harness, session) == []


def test_identifiers_are_removed_before_the_message_is_stored(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"))
    session = start(harness)["session"]

    say(harness, session, "me llamo Ana Gómez, cel 3001234567, tengo acidez")

    assert history(harness, session)[0]["content"] == (
        "me llamo [nombre], cel [teléfono], tengo acidez"
    )


def test_a_person_cannot_reach_chats_of_other_channels(database: SqliteDatabase) -> None:
    harness = build(database)
    other = whatsapp_chat(database)

    assert harness.client.get(f"/api/me/sessions/{other}").status_code == 404
    assert harness.client.get(f"/api/me/sessions/{other}/messages").status_code == 404
    assert say(harness, other, "hola").status_code == 404
    assert harness.client.get("/api/me/sessions/no-existe").status_code == 404


def test_a_model_failure_tells_the_person_what_to_do(database: SqliteDatabase) -> None:
    harness = build(database, LanguageModelError("sin modelo"))
    session = start(harness)["session"]

    response = say(harness, session, "tengo acidez")

    assert response.status_code == 502 and "123" in response.json()["detail"]
    assert history(harness, session) == []


# --- Consentimiento (HU-01) -------------------------------------------------------------


def test_without_consent_nothing_is_attended_or_stored(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"), consent_required=True)
    session = start(harness)

    response = say(harness, session["session"], "tengo sangrado vaginal")

    assert session["consent"] == "pendiente" and session["consent_required"]
    assert response.status_code == 403
    assert history(harness, session["session"]) == []


def test_accepting_consent_opens_the_conversation(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"), consent_required=True)
    session = start(harness)["session"]

    decided = harness.client.post(
        f"/api/me/sessions/{session}/consent", json={"accepted": True}
    ).json()

    assert decided["consent"] == "aceptado"
    assert say(harness, session, "tengo acidez").json()["reply"] == REPLY
    row = database.query("SELECT consent_status, consent_at FROM users WHERE id = ?", (session,))[0]
    assert row["consent_status"] == "aceptado" and row["consent_at"]


def test_rejecting_consent_keeps_the_conversation_closed(database: SqliteDatabase) -> None:
    harness = build(database, consent_required=True)
    session = start(harness)["session"]

    decided = harness.client.post(
        f"/api/me/sessions/{session}/consent", json={"accepted": False}
    ).json()

    assert decided["consent"] == "rechazado"
    assert say(harness, session, "tengo acidez").status_code == 403


def test_consent_is_not_asked_when_the_mode_is_off(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"))
    session = start(harness)

    assert session["consent_required"] is False
    assert say(harness, session["session"], "tengo acidez").status_code == 200


# --- Alertas para supervisión (HU-17) ---------------------------------------------------


def test_alert_inbox_lists_recent_alerts_with_their_chat(database: SqliteDatabase) -> None:
    harness = build(database, agent_json("Orientación"))
    first, second = start(harness)["session"], start(harness)["session"]
    say(harness, first, "tengo la presión alta")
    say(harness, second, "tengo sangrado vaginal")

    alerts = harness.client.get("/api/alerts").json()

    assert [alert["severity"] for alert in alerts] == ["urgencia_inmediata", "consulta_prioritaria"]
    assert alerts[0]["chat_id"] == second and alerts[0]["channel"] == "web"
    assert alerts[1]["chat_id"] == first and alerts[1]["rule_ids"]
    assert PRIORITY_MESSAGE in history(harness, first)[1]["content"]
    assert len(harness.client.get("/api/alerts?limit=1").json()) == 1


def test_evidence_in_the_team_view_carries_its_provenance(database: SqliteDatabase) -> None:
    harness = build(database, citing(agent_json(REPLY), "E1"))
    chat_id = harness.client.post("/api/chats").json()["id"]

    body = harness.client.post(
        f"/api/chats/{chat_id}/messages", json={"text": "tengo acidez", "after": 0}
    ).json()

    provenance = body["messages"][-1]["trace"]["evidence"][0]["provenance"]
    assert provenance["review"] == "revisada_por_el_equipo"
    assert provenance["sources"][0]["entity"] == "OPS"
