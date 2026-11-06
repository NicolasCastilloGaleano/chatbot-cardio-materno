"""Pruebas del modo activo de la indagación en el servicio (HU-11, fase 3, ADR 0017)."""

from dataclasses import replace

from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    CLOSING_TEXT,
    NO_INFORMATION_TEXT,
)
from cardio_materno.application.inquiry_policy import InquiryActivation
from cardio_materno.application.inquiry_turn import INQUIRY_FALLBACK_QUESTION
from cardio_materno.domain.knowledge import (
    EvidenceItem,
    Focus,
    RetrievalResult,
    RetrievalStatus,
)
from cardio_materno.domain.trace import TurnMode
from tests.unit.fakes import FakeRetriever, ScriptedAgent, agent_json, knowledge_entry, make_service
from tests.unit.test_inquiry_observation import inquiry_of, promising, reporting, send_all

ACTIVE = {"inquiry_activation": InquiryActivation.ACTIVE, "inquiry_prompt": "INDAGAR"}


def nothing(score: float = 0.30) -> RetrievalResult:
    """Sin evidencia ni candidatos cercanos."""
    return RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=score)


def clear(score: float = 0.74) -> RetrievalResult:
    """Evidencia clara: dos candidatos de la misma categoría sobre el umbral para responder."""
    found = promising(score)
    second = EvidenceItem("C2", found.candidates[0].entry, score - 0.01)
    return replace(found, candidates=(*found.candidates, second))


def test_promising_evidence_is_inquired_with_verified_questions() -> None:
    turn = reporting("respuesta") | {"questions": ["¿Dónde arde?", "Es reflujo."]}

    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), turn)

    assert result.reply == "¿Dónde arde?"
    assert inquiry_of(result).mode is TurnMode.INQUIRE and inquiry_of(result).applied
    assert result.trace is not None and result.trace.evidence == ()
    assert result.trace.grounding is not None and result.trace.grounding.dropped == ("Es reflujo.",)


def test_inquiry_receives_the_candidates_and_its_own_prompt() -> None:
    agent = ScriptedAgent(reporting("respuesta"))
    make_service(agent, config=ACTIVE, retriever=FakeRetriever(promising(0.55))).send("ardor raro")

    context = "\n".join(message.content for message in agent.responder.calls[0])
    assert "INDAGAR" in context and "CANDIDATOS" in context and "[C1]" in context


def test_without_valid_questions_the_fixed_question_is_asked() -> None:
    turn = reporting("respuesta") | {"questions": ["Es acidez."]}

    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), turn)

    assert result.reply == INQUIRY_FALLBACK_QUESTION


def test_clear_evidence_is_answered_without_inquiry() -> None:
    (result,) = send_all(ACTIVE, FakeRetriever(clear()), reporting("respuesta"))

    assert inquiry_of(result).mode is TurnMode.ANSWER and result.reply == "respuesta"


def test_nothing_close_abstains_and_then_closes() -> None:
    turns = (reporting("r", thread_action="nuevo"), reporting("r"))

    first, second = send_all(ACTIVE, FakeRetriever(nothing(), nothing(0.32)), *turns)

    assert (inquiry_of(first).mode, first.reply) == (TurnMode.ABSTAIN, ABSTENTION_TEXT)
    assert (inquiry_of(second).mode, second.reply) == (TurnMode.CLOSE, CLOSING_TEXT)


def test_inquiry_then_answer_when_the_details_bring_clear_evidence() -> None:
    turns = (reporting("r", thread_action="nuevo"), reporting("respuesta"))

    first, second = send_all(ACTIVE, FakeRetriever(promising(0.55), clear()), *turns)

    assert inquiry_of(first).mode is TurnMode.INQUIRE
    assert inquiry_of(second).mode is TurnMode.ANSWER and second.reply == "respuesta"


def test_observe_mode_keeps_the_previous_reply() -> None:
    observe = {"inquiry_activation": InquiryActivation.OBSERVE}

    (result,) = send_all(observe, FakeRetriever(promising(0.55)), reporting("respuesta"))

    assert result.reply == "respuesta" and not inquiry_of(result).applied


def test_candidate_entries_are_never_cited_in_an_inquiry_turn() -> None:
    entry = knowledge_entry(answer="Afirmación de salud del registro.")
    found = replace(promising(0.55), candidates=(EvidenceItem("C1", entry, 0.55),))

    (result,) = send_all(ACTIVE, FakeRetriever(found), reporting("r"))

    assert "Afirmación de salud" not in result.reply and result.trace is not None
    assert result.trace.cited_evidence == ()


def test_a_question_of_information_is_answered_and_not_inquired() -> None:
    turn = reporting("respuesta") | {"asks_information": True}

    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), turn)

    assert inquiry_of(result).informational and result.reply == "respuesta"


def test_a_message_without_symptoms_is_informational() -> None:
    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), agent_json("respuesta"))

    assert inquiry_of(result).mode is TurnMode.ANSWER and result.reply == "respuesta"


def test_a_question_without_evidence_gets_the_abstention_without_asking_for_symptoms() -> None:
    turn = reporting("r") | {"asks_information": True}
    near = replace(promising(0.45), items=(), status=RetrievalStatus.INSUFFICIENT)

    (result,) = send_all(ACTIVE, FakeRetriever(near), turn)

    assert (inquiry_of(result).mode, result.reply) == (TurnMode.ABSTAIN, NO_INFORMATION_TEXT)


def test_a_report_without_evidence_still_asks_for_details() -> None:
    near = replace(promising(0.45), items=(), status=RetrievalStatus.INSUFFICIENT)

    turn = reporting("r") | {"wants_guidance": True}

    (result,) = send_all(ACTIVE, FakeRetriever(near), turn)

    assert (inquiry_of(result).mode, result.reply) == (TurnMode.ABSTAIN, ABSTENTION_TEXT)


def test_the_next_inquiry_does_not_repeat_the_same_questions() -> None:
    asked = "¿El ardor sube hacia la garganta?"
    first = reporting("r", thread_action="nuevo") | {"questions": [asked]}
    second = reporting("r") | {"questions": [asked, "¿Te pasa también al caminar?"]}

    _, result = send_all(ACTIVE, FakeRetriever(promising(0.55)), first, second)

    assert result.reply == "¿Te pasa también al caminar?"
    assert result.trace is not None and result.trace.grounding is not None
    assert asked in result.trace.grounding.dropped


def test_if_every_question_repeats_the_fixed_question_is_used() -> None:
    asked = "¿El ardor sube hacia la garganta?"
    first = reporting("r", thread_action="nuevo") | {"questions": [asked]}
    second = reporting("r") | {"questions": ["¿El ardor te sube hacia la garganta?"]}

    _, result = send_all(ACTIVE, FakeRetriever(promising(0.55)), first, second)

    assert result.reply == INQUIRY_FALLBACK_QUESTION


def test_answers_only_use_solving_records_and_drop_questions() -> None:
    solving = knowledge_entry("s", answer="Prefiere verduras. ¿Comes sal?")
    inquiring = replace(knowledge_entry("i", answer="Describe tu dieta."), focus=Focus.INQUIRE)
    items = (EvidenceItem("E1", inquiring, 0.74), EvidenceItem("E2", solving, 0.73))
    found = replace(clear(), items=items)
    sentences = [
        {"text": "Prefiere verduras.", "evidence_id": "E2"},
        {"text": "¿Comes sal?", "evidence_id": "E2"},
    ]
    agent = ScriptedAgent(reporting("r") | {"sentences": sentences})

    result = make_service(agent, config=ACTIVE, retriever=FakeRetriever(found)).send("x")

    context = "\n".join(message.content for message in agent.responder.calls[0])
    assert result.reply == "Prefiere verduras."
    assert "Describe tu dieta" not in context


def test_evidence_with_only_inquiry_records_is_not_an_answer() -> None:
    inquiring = replace(knowledge_entry(answer="Describe tu dieta."), focus=Focus.INQUIRE)
    found = replace(clear(), items=(EvidenceItem("E1", inquiring, 0.74),))
    turn = reporting("r") | {"questions": ["¿Qué comes?"]}

    (result,) = send_all(ACTIVE, FakeRetriever(found), turn)

    assert inquiry_of(result).mode is TurnMode.INQUIRE and result.reply == "¿Qué comes?"
