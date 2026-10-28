"""Pruebas del turno de indagación verificado (HU-11, fase 3, ADR 0017)."""

import pytest

from cardio_materno.application.agent_turn import inquiry_schema, parse_inquiry
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import CANDIDATES_HEADER, format_candidates_context
from cardio_materno.application.inquiry_turn import INQUIRY_FALLBACK_QUESTION, compose_inquiry
from cardio_materno.domain.grounding import GroundingPolicy, has_question, verify_inquiry
from cardio_materno.domain.knowledge import EvidenceItem
from tests.unit.fakes import knowledge_entry

POLICY = GroundingPolicy()


@pytest.mark.parametrize(
    "sentence",
    [
        "¿Dónde sientes el ardor?",
        "¿Desde cuándo te pasa?",
        "Gracias por contarme.",
        "¿Tienes 34 semanas de embarazo?",  # el 34 lo dijo la persona
    ],
)
def test_short_questions_courtesy_and_said_numbers_are_accepted(sentence: str) -> None:
    kept, dropped = verify_inquiry([sentence], ["tengo 34 semanas y un ardor raro"], POLICY)

    assert kept == (sentence,) and dropped == ()


@pytest.mark.parametrize(
    "sentence",
    [
        "La acidez es común en el embarazo.",  # afirmación de salud
        "¿Te tomaste 2 pastillas?",  # número que la persona no dijo
        "¿" + " ".join(["palabra"] * 21) + "?",  # demasiado larga
    ],
    ids=["afirmacion", "numero-no-dicho", "larga"],
)
def test_claims_unsaid_numbers_and_long_sentences_are_dropped(sentence: str) -> None:
    kept, dropped = verify_inquiry([sentence], ["tengo un ardor raro"], POLICY)

    assert kept == () and dropped == (sentence,)


def test_the_turn_is_limited_to_the_maximum_of_sentences() -> None:
    sentences = ["¿Dónde?", "¿Desde cuándo?", "¿Cómo es?", "¿A quién le pasa?"]

    kept, dropped = verify_inquiry(sentences, [], GroundingPolicy(max_inquiry_sentences=3))

    assert kept == tuple(sentences[:3]) and dropped == ("¿A quién le pasa?",)


def test_compose_inquiry_keeps_verified_questions_and_records_the_check() -> None:
    draft = ["Gracias por contarme.", "¿Dónde sientes el ardor?", "Puede ser reflujo."]

    reply = compose_inquiry(draft, ["tengo un ardor raro"], POLICY)

    assert reply.text == "Gracias por contarme. ¿Dónde sientes el ardor?"
    assert reply.cited == () and reply.check.dropped == ("Puede ser reflujo.",)
    assert (reply.check.supported, reply.check.total) == (2, 3)


def test_without_a_valid_question_the_fixed_question_is_used() -> None:
    reply = compose_inquiry(["Gracias.", "Es acidez."], ["ardor"], POLICY)

    assert reply.text == f"Gracias. {INQUIRY_FALLBACK_QUESTION}"
    assert has_question([reply.text]) and not has_question(["Gracias."])


def test_inquiry_schema_and_parser() -> None:
    schema = inquiry_schema(3)

    assert schema["properties"]["sentences"]["maxItems"] == 3
    assert parse_inquiry({"sentences": [" ¿Dónde? ", "", 3]}) == ("¿Dónde?",)
    with pytest.raises(LanguageModelError, match="sentences"):
        parse_inquiry({"sentences": []})
    with pytest.raises(LanguageModelError, match="sentences"):
        parse_inquiry({"sentences": "¿Dónde?"})


def test_candidates_are_presented_as_not_evidence() -> None:
    context = format_candidates_context([EvidenceItem("C1", knowledge_entry(), 0.45)], 700)

    assert context.startswith(CANDIDATES_HEADER) and "[C1]" in context
    assert "NO son evidencia" in CANDIDATES_HEADER
