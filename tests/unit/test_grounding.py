"""Pruebas de la verificación determinista del respaldo (HU-02, ADR 0010)."""

import pytest

from cardio_materno.application.agent_turn import DraftSentence
from cardio_materno.application.grounded_reply import (
    LITERAL_TEMPLATE,
    compose_grounded_reply,
)
from cardio_materno.domain.grounding import (
    GroundingPolicy,
    content_stems,
    has_placeholder,
    is_allowed_without_citation,
    is_supported,
    remove_placeholders,
    stated_numbers,
    support_ratio,
    unstated_details,
)
from tests.unit.fakes import evidence_result, knowledge_entry

POLICY = GroundingPolicy()
EVIDENCE = (
    "Describe si es ardor que sube hacia el pecho, cuánto tarda en aparecer después de comer "
    "y qué alimentos lo desencadenan. Indica las semanas de embarazo. Si la molestia es intensa "
    "o hay dolor de cabeza o visión alterada, necesita atención obstétrica inmediata."
)


def test_content_stems_ignore_accents_stopwords_short_words_and_numbers() -> None:
    stems = content_stems("¿Cuánto tarda la Acidez después de 2 comidas en el embarazo?", POLICY)

    assert stems == {"tarda", "acide", "comid", "embar"}


def test_close_paraphrase_is_supported() -> None:
    sentence = "Si tienes dolor de cabeza o visión alterada, necesitas atención inmediata."

    assert is_supported(sentence, EVIDENCE, POLICY)


@pytest.mark.parametrize(
    "sentence",
    [
        "La acidez se debe a los cambios hormonales y a la presión del útero.",
        "Come yogur, avena, almendras y nueces.",
        "Es importante que hables con tu médico.",
    ],
    ids=["causa-inventada", "dieta-inventada", "aviso-suavizado"],
)
def test_invented_or_softened_sentences_are_not_supported(sentence: str) -> None:
    assert not is_supported(sentence, EVIDENCE, POLICY)


def test_numbers_must_appear_in_the_evidence() -> None:
    assert not is_supported("Indica las 34 semanas de embarazo.", EVIDENCE, POLICY)
    assert is_supported("Indica las 34 semanas de embarazo.", EVIDENCE + " 34", POLICY)


def test_support_ratio_of_sentence_without_content_words_is_one() -> None:
    assert support_ratio("Sí, así es.", EVIDENCE, POLICY) == 1.0


@pytest.mark.parametrize(
    "sentence",
    [
        "¿Desde cuándo lo sientes?",
        "Gracias por escribirme.",
        "Entiendo tu preocupación.",
        "Sobre el partido no puedo ayudarte.",
    ],
)
def test_harmless_sentences_are_allowed_without_citation(sentence: str) -> None:
    assert is_allowed_without_citation(sentence, "¿quién ganó el partido? y tengo acidez", POLICY)


@pytest.mark.parametrize(
    "sentence",
    [
        "Toma infusiones de jengibre o manzanilla.",
        "La acidez es normal en el embarazo.",
        "¿Tomas 2 pastillas al día?",
        "Sobre la acidez no puedo ayudarte, pero evita el café.",
    ],
    ids=["consejo", "afirmacion", "pregunta-con-numero", "rechazo-con-consejo"],
)
def test_health_claims_are_not_allowed_without_citation(sentence: str) -> None:
    assert not is_allowed_without_citation(sentence, "tengo acidez", POLICY)


def test_long_question_is_not_allowed_without_citation() -> None:
    question = "¿" + " ".join(["palabra"] * (POLICY.max_free_words + 1)) + "?"

    assert not is_allowed_without_citation(question, "", POLICY)


def test_only_the_first_allowed_free_sentences_are_kept() -> None:
    items = evidence_result(knowledge_entry(answer=EVIDENCE)).items
    draft = [
        DraftSentence("Describe si el ardor sube hacia el pecho.", "E1"),
        DraftSentence("Gracias por escribirme."),
        DraftSentence("Entiendo tu preocupación."),
        DraftSentence("¿Desde cuándo?"),
    ]

    reply = compose_grounded_reply(draft, items, "tengo acidez", GroundingPolicy())

    assert reply.text == (
        "Describe si el ardor sube hacia el pecho. Gracias por escribirme. "
        "Entiendo tu preocupación."
    )
    assert reply.check.dropped == ("¿Desde cuándo?",) and not reply.check.literal


def test_literal_fallback_uses_the_first_cited_entry() -> None:
    items = evidence_result(knowledge_entry("k1"), knowledge_entry("k2", answer="Otra cosa.")).items
    draft = [DraftSentence("Algo inventado sobre medicamentos.", "E2")]

    reply = compose_grounded_reply(draft, items, "x", POLICY)

    assert reply.text == LITERAL_TEMPLATE.format(answer="Otra cosa.")
    assert reply.cited == ("E2",) and reply.check.literal


def test_referral_without_support_in_the_cited_entry_is_rejected() -> None:
    assert not is_supported("Acude de inmediato a urgencias o llama al 123.", EVIDENCE, POLICY)
    assert not is_supported("Llama al 123 y toma ibuprofeno con agua.", EVIDENCE, POLICY)


def test_referral_supported_by_the_cited_entry_is_accepted() -> None:
    evidence = EVIDENCE + " Si no puedes llegar, acude a urgencias o llama a la línea 123."

    assert is_supported("Acude a urgencias o llama a la línea 123.", evidence, POLICY)


# --- Datos que la persona no escribió (B-021, incidente del 2026-10-11) -------------------


def test_stated_numbers_include_digits_and_spelled_numbers() -> None:
    assert stated_numbers("tengo ocho meses y 2 hijos, un bebé") == {"8", "2"}


def test_symptom_with_a_number_the_person_never_wrote_is_flagged() -> None:
    symptoms = ["acidez en el embarazo de 34 semanas", "dolor de cabeza", "fiebre de 2 días"]

    assert unstated_details(symptoms, ["tengo acidez en el embarazo", "fiebre hace dos días"]) == (
        "acidez en el embarazo de 34 semanas",
    )


def test_numbers_said_in_digits_or_words_are_not_flagged() -> None:
    symptoms = ["embarazo de 8 meses", "embarazo de 34 semanas"]

    assert unstated_details(symptoms, ["tengo ocho meses", "o sea 34 semanas"]) == ()


def test_symptoms_with_prompt_placeholders_are_flagged() -> None:
    symptoms = ["Contracciones desde hace [N] días", "Piel muy amarilla: [lo que describió], bebé"]

    assert unstated_details(symptoms, ["tengo contracciones", "mi bebé está amarillo"]) == tuple(
        symptoms
    )
    assert has_placeholder("[síntoma]") and not has_placeholder("presión 190/110")


def test_placeholders_are_removed_from_text() -> None:
    assert remove_placeholders("Fiebre: [lo que describió la persona], embarazo") == (
        "Fiebre: , embarazo"
    )
    assert remove_placeholders("acidez en el embarazo de [N] semanas") == (
        "acidez en el embarazo de semanas"
    )
