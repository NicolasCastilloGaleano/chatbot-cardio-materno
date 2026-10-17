"""Pruebas del adaptador web local sin Ollama."""

from typing import Any

from fastapi.testclient import TestClient

from cardio_materno.adapters.inbound.api.web_app import create_app
from cardio_materno.application.errors import LanguageModelError
from tests.unit.fakes import (
    InMemoryThreadRepository,
    ScriptedAgent,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    scoped,
)


def make_client(
    turns: list[dict[str, Any] | Exception],
    with_alarm_policy: bool = False,
) -> tuple[TestClient, InMemoryThreadRepository]:
    """Construye el cliente HTTP con agente guionizado y repositorio en memoria."""
    agent = ScriptedAgent(*turns)
    repository = InMemoryThreadRepository()
    config = {"alarm_policy": make_alarm_policy()} if with_alarm_policy else None
    service = make_service(agent, repo=repository, config=config)
    entry = knowledge_entry(answer="Orientación validada para la prueba")
    return TestClient(create_app(service, repository, [entry])), repository


def test_send_message_returns_trace_and_full_evidence() -> None:
    client, _ = make_client(
        [
            scoped(
                {
                    "thread_action": "nuevo",
                    "domain": "materno_infantil",
                    "summary": "Consulta de alimentación",
                    "reported_symptoms": ["acidez"],
                    "reported_signs": [],
                    "search_query": "alimentación y acidez",
                    "scope": "en_alcance",
                    "scope_reason": "consulta de salud",
                    "reply": "Orientación validada para la prueba",
                    "evidence_ids": ["E1"],
                },
                "en_alcance",
            )
        ]
    )

    response = client.post("/api/messages", json={"text": "Tengo acidez"})

    assert response.status_code == 200
    result = response.json()
    assert result["reply"] == "Orientación validada para la prueba"
    assert result["thread"]["summary"] == "Consulta de alimentación"
    assert result["trace"]["reported_symptoms"] == ["acidez"]
    assert result["trace"]["search_query"] == "alimentación y acidez"
    assert result["trace"]["evidence"][0]["answer"] == "Orientación validada para la prueba"
    assert result["trace"]["cited_evidence"] == ["E1"]


def test_out_of_scope_reply_is_not_added_to_persisted_thread() -> None:
    client, repository = make_client(
        [
            scoped(
                {
                    "thread_action": "nuevo",
                    "domain": "ninguno",
                    "summary": "sin hilo",
                    "reported_symptoms": [],
                    "reported_signs": [],
                    "search_query": "",
                    "scope": "fuera_de_alcance",
                    "scope_reason": "tema ajeno",
                    "reply": "No puedo ayudar con ese tema.",
                    "evidence_ids": [],
                },
                "fuera_de_alcance",
                "tema ajeno",
            )
        ]
    )

    response = client.post("/api/messages", json={"text": "¿Quién ganó el partido?"})

    assert response.status_code == 200
    assert response.json()["out_of_scope"] is True
    assert response.json()["thread"] is None
    assert repository.list_threads() == []


def test_saved_thread_can_be_listed_and_opened_read_only() -> None:
    client, _ = make_client(
        [
            {
                "thread_action": "nuevo",
                "domain": "materno_infantil",
                "summary": "Consulta guardada",
                "reported_symptoms": [],
                "reported_signs": [],
                "search_query": "consulta guardada",
                "scope": "en_alcance",
                "scope_reason": "",
                "reply": "Orientación validada para la prueba",
                "evidence_ids": ["E1"],
            }
        ]
    )
    client.post("/api/messages", json={"text": "Consulta guardada"})

    listed = client.get("/api/threads")
    thread_id = listed.json()[0]["id"]
    history = client.get(f"/api/threads/{thread_id}")

    assert listed.status_code == 200
    assert len(history.json()["messages"]) == 2
    assert history.json()["messages"][1]["trace"]["evidence"][0]["question"] == "¿Pregunta?"


def test_missing_thread_returns_not_found() -> None:
    client, _ = make_client([])

    assert client.get("/api/threads/inexistente").status_code == 404


def test_language_model_failure_is_a_clear_gateway_error() -> None:
    client, _ = make_client([LanguageModelError("detalle interno")])

    response = client.post("/api/messages", json={"text": "Tengo una consulta"})

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "No se pudo generar la respuesta. Puedes intentarlo de nuevo."
    )


def test_new_session_closes_the_active_thread() -> None:
    client, repository = make_client(
        [
            {
                "thread_action": "nuevo",
                "domain": "materno_infantil",
                "summary": "Consulta guardada",
                "reported_symptoms": [],
                "reported_signs": [],
                "search_query": "consulta guardada",
                "scope": "en_alcance",
                "scope_reason": "",
                "reply": "Orientación validada para la prueba",
                "evidence_ids": ["E1"],
            }
        ]
    )
    client.post("/api/messages", json={"text": "Consulta guardada"})

    assert client.post("/api/session/end").json() == {"status": "cerrada"}
    assert repository.list_threads()[0].is_open is False


def test_message_request_rejects_empty_text() -> None:
    client, _ = make_client([])

    assert client.post("/api/messages", json={"text": "   "}).status_code == 422


def test_local_page_and_script_are_served() -> None:
    client, _ = make_client([])

    page = client.get("/")
    script = client.get("/static/app.js")
    styles = client.get("/static/styles.css")

    assert page.status_code == 200
    assert "Hilos guardados" in page.text
    assert script.status_code == 200
    assert "showAudit" in script.text
    assert 'event.key !== "Enter" || event.shiftKey || event.isComposing' in script.text
    assert "Estoy procesando tu mensaje" in script.text
    assert styles.status_code == 200
    assert ".messages" in styles.text and "overflow-y: auto" in styles.text
    assert ".side-column" in styles.text and "height: 100%" in styles.text


def test_immediate_alarm_is_returned_without_calling_agent() -> None:
    client, repository = make_client([], with_alarm_policy=True)

    response = client.post("/api/messages", json={"text": "tengo sangrado vaginal"})

    assert response.status_code == 200
    assert response.json()["trace"] is None
    assert response.json()["alerts"][0]["severity"] == "urgencia_inmediata"
    assert len(repository.list_threads()) == 1
