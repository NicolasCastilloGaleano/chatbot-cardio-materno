"""Pruebas del modo activo de la indagación en el servicio (HU-11, fase 3, ADR 0017)."""

from dataclasses import replace

from cardio_materno.application.grounded_reply import ABSTENTION_TEXT, CLOSING_TEXT
from cardio_materno.application.inquiry_policy import InquiryActivation
from cardio_materno.application.inquiry_turn import INQUIRY_FALLBACK_QUESTION
from cardio_materno.domain.knowledge import EvidenceItem, RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import TurnMode
from tests.unit.fakes import FakeRetriever, ScriptedAgent, agent_json, knowledge_entry, make_service
from tests.unit.test_inquiry_observation import inquiry_of, promising, send_all

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
    turn = agent_json("respuesta") | {"questions": ["¿Dónde arde?", "Es reflujo."]}

    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), turn)

    assert result.reply == "¿Dónde arde?"
    assert inquiry_of(result).mode is TurnMode.INQUIRE and inquiry_of(result).applied
    assert result.trace is not None and result.trace.evidence == ()
    assert result.trace.grounding is not None and result.trace.grounding.dropped == ("Es reflujo.",)


def test_inquiry_receives_the_candidates_and_its_own_prompt() -> None:
    agent = ScriptedAgent(agent_json("respuesta"))
    make_service(agent, config=ACTIVE, retriever=FakeRetriever(promising(0.55))).send("ardor raro")

    context = "\n".join(message.content for message in agent.responder.calls[0])
    assert "INDAGAR" in context and "CANDIDATOS" in context and "[C1]" in context


def test_without_valid_questions_the_fixed_question_is_asked() -> None:
    turn = agent_json("respuesta") | {"questions": ["Es acidez."]}

    (result,) = send_all(ACTIVE, FakeRetriever(promising(0.55)), turn)

    assert result.reply == INQUIRY_FALLBACK_QUESTION


def test_clear_evidence_is_answered_without_inquiry() -> None:
    (result,) = send_all(ACTIVE, FakeRetriever(clear()), agent_json("respuesta"))

    assert inquiry_of(result).mode is TurnMode.ANSWER and result.reply == "respuesta"


def test_nothing_close_abstains_and_then_closes() -> None:
    turns = (agent_json("r", thread_action="nuevo"), agent_json("r"))

    first, second = send_all(ACTIVE, FakeRetriever(nothing(), nothing(0.32)), *turns)

    assert (inquiry_of(first).mode, first.reply) == (TurnMode.ABSTAIN, ABSTENTION_TEXT)
    assert (inquiry_of(second).mode, second.reply) == (TurnMode.CLOSE, CLOSING_TEXT)


def test_inquiry_then_answer_when_the_details_bring_clear_evidence() -> None:
    turns = (agent_json("r", thread_action="nuevo"), agent_json("respuesta"))

    first, second = send_all(ACTIVE, FakeRetriever(promising(0.55), clear()), *turns)

    assert inquiry_of(first).mode is TurnMode.INQUIRE
    assert inquiry_of(second).mode is TurnMode.ANSWER and second.reply == "respuesta"


def test_observe_mode_keeps_the_previous_reply() -> None:
    observe = {"inquiry_activation": InquiryActivation.OBSERVE}

    (result,) = send_all(observe, FakeRetriever(promising(0.55)), agent_json("respuesta"))

    assert result.reply == "respuesta" and not inquiry_of(result).applied


def test_candidate_entries_are_never_cited_in_an_inquiry_turn() -> None:
    entry = knowledge_entry(answer="Afirmación de salud del registro.")
    found = replace(promising(0.55), candidates=(EvidenceItem("C1", entry, 0.55),))

    (result,) = send_all(ACTIVE, FakeRetriever(found), agent_json("r"))

    assert "Afirmación de salud" not in result.reply and result.trace is not None
    assert result.trace.cited_evidence == ()
