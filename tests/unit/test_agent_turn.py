"""Pruebas de los contratos JSON de las llamadas de análisis y de respuesta."""

from typing import Any

import pytest

from cardio_materno.application.agent_turn import (
    ANALYSIS_SCHEMA,
    NO_CITATION,
    DraftSentence,
    Scope,
    ThreadAction,
    grounded_reply_schema,
    parse_analysis,
    parse_grounded_reply,
    parse_reply,
    reply_schema,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import Domain


def analysis_json(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_action": "continuar",
        "domain": "materno_infantil",
        "summary": "resumen",
        "reported_symptoms": [],
        "scope": "en_alcance",
        "scope_reason": "",
    }
    return base | overrides


# --- Análisis ---------------------------------------------------------------------------------


def test_valid_analysis_is_parsed_and_trimmed() -> None:
    turn = parse_analysis(analysis_json(thread_action="nuevo", summary="  s  "))

    assert turn.thread_action is ThreadAction.NEW
    assert turn.domain is Domain.MATERNAL_CHILD
    assert turn.summary == "s"


@pytest.mark.parametrize(
    ("field", "value"),
    [("thread_action", "cerrar"), ("domain", "oncologia"), ("summary", "   "), ("summary", 42)],
)
def test_invalid_analysis_values_raise_error(field: str, value: Any) -> None:
    with pytest.raises(LanguageModelError, match=field):
        parse_analysis(analysis_json(**{field: value}))


def test_missing_analysis_field_raises_error() -> None:
    data = analysis_json()
    del data["summary"]

    with pytest.raises(LanguageModelError, match="summary"):
        parse_analysis(data)


def test_reported_symptoms_are_trimmed_and_empty_items_dropped() -> None:
    turn = parse_analysis(analysis_json(reported_symptoms=[" fiebre ", "", "  "]))

    assert turn.reported_symptoms == ("fiebre",)


@pytest.mark.parametrize("value", ["fiebre", [1, 2], None])
def test_reported_symptoms_must_be_a_list_of_texts(value: Any) -> None:
    with pytest.raises(LanguageModelError, match="reported_symptoms"):
        parse_analysis(analysis_json(reported_symptoms=value))


def test_analysis_schema_has_no_reply_and_lists_allowed_values() -> None:
    properties = ANALYSIS_SCHEMA["properties"]

    assert "reply" not in properties
    assert properties["thread_action"]["enum"] == ["continuar", "nuevo"]
    assert properties["domain"]["enum"] == ["materno_infantil", "cardiovascular", "ninguno"]
    assert properties["scope"]["enum"] == ["en_alcance", "conversacional", "fuera_de_alcance"]
    assert set(ANALYSIS_SCHEMA["required"]) == {
        "thread_action",
        "domain",
        "summary",
        "reported_symptoms",
        "scope",
        "scope_reason",
    }


def test_scope_and_reason_are_parsed() -> None:
    turn = parse_analysis(analysis_json(scope="fuera_de_alcance", scope_reason=" deportes "))

    assert turn.scope is Scope.OUT_OF_SCOPE
    assert turn.scope_reason == "deportes"


@pytest.mark.parametrize(("field", "value"), [("scope", "quizas"), ("scope_reason", 3)])
def test_invalid_scope_fields_raise_error(field: str, value: Any) -> None:
    with pytest.raises(LanguageModelError, match=field):
        parse_analysis(analysis_json(**{field: value}))


# --- Respuesta --------------------------------------------------------------------------------


def test_valid_reply_with_citations_is_parsed_without_duplicates() -> None:
    turn = parse_reply({"reply": " hola ", "evidence_ids": ["E1", "E2", "E1"]}, ["E1", "E2"])

    assert turn.reply == "hola"
    assert turn.evidence_ids == ("E1", "E2")


def test_reply_citing_unoffered_label_raises_error() -> None:
    with pytest.raises(LanguageModelError, match="E3"):
        parse_reply({"reply": "hola", "evidence_ids": ["E3"]}, ["E1"])


@pytest.mark.parametrize(
    "data", [{"reply": "", "evidence_ids": []}, {"evidence_ids": []}, {"reply": "x"}]
)
def test_invalid_reply_raises_error(data: dict[str, Any]) -> None:
    with pytest.raises(LanguageModelError):
        parse_reply(data, [])


def test_reply_schema_restricts_citations_to_offered_labels() -> None:
    with_labels = reply_schema(["E1", "E2"])["properties"]["evidence_ids"]
    without_labels = reply_schema([])["properties"]["evidence_ids"]

    assert with_labels["items"]["enum"] == ["E1", "E2"]
    assert without_labels["maxItems"] == 0


# --- Respuesta frase por frase (ADR 0010) --------------------------------------------------


def test_grounded_reply_schema_restricts_each_citation_to_offered_labels_or_none() -> None:
    schema = grounded_reply_schema(["E1", "E2"])

    sentence = schema["properties"]["sentences"]["items"]
    assert sentence["properties"]["evidence_id"]["enum"] == ["E1", "E2", NO_CITATION]
    assert sentence["required"] == ["text", "evidence_id"]
    assert schema["properties"]["sentences"]["minItems"] == 1


def test_grounded_reply_is_parsed_and_empty_sentences_are_dropped() -> None:
    data = {
        "sentences": [
            {"text": " Come poco. ", "evidence_id": "E1"},
            {"text": "  ", "evidence_id": "E1"},
            {"text": "¿Desde cuándo?", "evidence_id": NO_CITATION},
        ]
    }

    assert parse_grounded_reply(data, ["E1"]) == (
        DraftSentence("Come poco.", "E1"),
        DraftSentence("¿Desde cuándo?", None),
    )


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"sentences": []},
        {"sentences": ["texto suelto"]},
        {"sentences": [{"text": "x", "evidence_id": "E9"}]},
        {"sentences": [{"text": "x"}]},
    ],
    ids=["sin-frases", "lista-vacia", "frase-sin-forma", "etiqueta-no-ofrecida", "sin-cita"],
)
def test_invalid_grounded_reply_raises_error(data: dict[str, Any]) -> None:
    with pytest.raises(LanguageModelError):
        parse_grounded_reply(data, ["E1"])
