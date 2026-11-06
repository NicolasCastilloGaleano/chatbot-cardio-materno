"""Pruebas de responder e indagar (HU-13, ADR 0019, paso 1.3)."""

from dataclasses import replace
from typing import Any

from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence_selection import SelectionActivation
from cardio_materno.application.grounded_reply import LITERAL_TEMPLATE
from cardio_materno.application.inquiry_policy import (
    InquiryActivation,
    InquiryPolicy,
    InquiryState,
    answer_only,
    answers_while_inquiring,
    mode_after_answer,
)
from cardio_materno.application.inquiry_turn import verified_question
from cardio_materno.domain.grounding import GroundingPolicy
from cardio_materno.domain.knowledge import RetrievalResult
from cardio_materno.domain.trace import InquiryTrace, SelectionVerdict, TurnMode
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    FakeRetriever,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    make_alarm_policy,
    make_service,
    selecting,
)
from tests.unit.test_inquiry_observation import inquiry_of, promising, reporting
from tests.unit.test_selected_answer import ACTIVE, USEFUL, clear_evidence, selection_of

REFLUX = "El reflujo causa ardor. Evita las comidas pesadas."
QUESTION = "¿Desde cuándo tienes el ardor?"
QUESTIONS = [QUESTION]
PARTIAL = selecting(reporting(USEFUL), "parcial", "E1.2")
ANSWERS = selecting(reporting(USEFUL), "responde", "E1.2")


def unclear() -> RetrievalResult:
    """Evidencia con un registro *Solucionar* sobre el umbral que no es clara para responder."""
    found = promising(0.55)
    entry = replace(found.items[0].entry, answer=REFLUX)
    item = replace(found.items[0], entry=entry)
    return replace(found, items=(item,), candidates=(replace(item, label="C1", score=0.55),))


def send(
    turn: dict[str, Any], retrieval: RetrievalResult, text: str = "tengo ardor", **config: Any
) -> tuple[TurnResult, ScriptedAgent]:
    agent = ScriptedAgent({"questions": QUESTIONS} | turn)
    service = make_service(agent, config=ACTIVE | config, retriever=FakeRetriever(retrieval))
    return service.send(text), agent


def prompts(agent: ScriptedAgent) -> list[str]:
    return [call[0].content for call in agent.responder.calls]


# --- Cuándo se responde y se pregunta ------------------------------------------------------------


def test_a_partial_verdict_answers_and_asks_one_question() -> None:
    result, agent = send(PARTIAL, clear_evidence())

    inquiry = inquiry_of(result)
    assert result.reply == f"{USEFUL}\n\n{QUESTION}"
    assert (inquiry.mode, inquiry.rule_mode) == (TurnMode.ANSWER_AND_INQUIRE, TurnMode.ANSWER)
    assert inquiry.turn == 1
    assert prompts(agent) == ["SELECTOR", "REDACTOR", "INDAGAR"]


def test_the_question_knows_what_was_answered_and_is_limited_to_one() -> None:
    _, agent = send(PARTIAL, clear_evidence())

    context = "\n".join(message.content for message in agent.responder.calls[2])
    assert USEFUL in context
    assert agent.responder.schemas[2]["properties"]["sentences"]["maxItems"] == 1


def test_unclear_evidence_answers_and_asks_even_if_the_selector_says_it_answers() -> None:
    result, agent = send(ANSWERS, unclear())

    inquiry = inquiry_of(result)
    assert result.reply == f"{USEFUL}\n\n{QUESTION}"
    assert (inquiry.mode, inquiry.rule_mode) == (TurnMode.ANSWER_AND_INQUIRE, TurnMode.INQUIRE)
    assert inquiry.turn == 1
    assert result.trace is not None and selection_of(result).applied


def test_clear_evidence_with_an_answer_does_not_ask() -> None:
    result, agent = send(ANSWERS, clear_evidence())

    assert result.reply == USEFUL and inquiry_of(result).mode is TurnMode.ANSWER
    assert prompts(agent) == ["SELECTOR", "REDACTOR"]


def test_a_literal_answer_can_also_ask() -> None:
    turn = selecting(reporting("El reflujo causa ardor."), "parcial", "E1.2")

    result, _ = send(turn, clear_evidence())

    assert result.reply == f"{LITERAL_TEMPLATE.format(answer=USEFUL)}\n\n{QUESTION}"


# --- Cuándo no se pregunta -----------------------------------------------------------------------


def test_a_direct_request_is_answered_without_questions() -> None:
    result, agent = send(PARTIAL | {"wants_guidance": True}, clear_evidence())

    assert result.reply == USEFUL and inquiry_of(result).mode is TurnMode.ANSWER
    assert "INDAGAR" not in prompts(agent)


def test_an_information_question_is_answered_without_questions() -> None:
    turn = selecting(agent_json(USEFUL), "parcial", "E1.2")

    result, agent = send(turn, clear_evidence())

    assert result.reply == USEFUL and "INDAGAR" not in prompts(agent)


def test_a_priority_alarm_is_never_followed_by_a_question() -> None:
    config = {"alarm_policy": make_alarm_policy()}

    result, agent = send(PARTIAL, clear_evidence(), text="tengo la presión alta", **config)

    assert PRIORITY_MESSAGE in result.reply and "INDAGAR" not in prompts(agent)
    assert QUESTION not in result.reply


def test_it_needs_both_modes_active() -> None:
    observing = {"inquiry_activation": InquiryActivation.OBSERVE}
    result, agent = send(ANSWERS, unclear(), **observing)
    assert QUESTION not in result.reply and "INDAGAR" not in prompts(agent)

    off = {"selection_activation": SelectionActivation.OBSERVE}
    result, agent = send(reporting("x"), unclear(), **off)
    assert result.reply == QUESTION and prompts(agent) == ["INDAGAR"]


# --- Si algo falla -------------------------------------------------------------------------------


def test_a_question_that_fails_verification_leaves_only_the_answer() -> None:
    result, _ = send(PARTIAL | {"questions": ["¿Llevas 30 días así?"]}, clear_evidence())

    inquiry = inquiry_of(result)
    assert result.reply == USEFUL
    assert (inquiry.mode, inquiry.turn) == (TurnMode.ANSWER, 0)


def test_a_failed_question_call_leaves_only_the_answer() -> None:
    result, _ = send(PARTIAL | {"questions": LanguageModelError("sin modelo")}, clear_evidence())

    assert result.reply == USEFUL and inquiry_of(result).mode is TurnMode.ANSWER


def test_without_visible_sentences_the_rule_just_inquires() -> None:
    result, agent = send(selecting(reporting("x"), "no_responde"), unclear())

    inquiry = inquiry_of(result)
    assert result.reply == QUESTION
    assert (inquiry.mode, inquiry.turn) == (TurnMode.INQUIRE, 1)
    assert prompts(agent) == ["SELECTOR", "INDAGAR"]


def test_if_the_selector_fails_the_rule_just_inquires() -> None:
    turn = reporting("x") | {"selection": LanguageModelError("sin modelo")}

    result, agent = send(turn, unclear())

    assert result.reply == QUESTION and inquiry_of(result).mode is TurnMode.INQUIRE
    assert prompts(agent) == ["SELECTOR", "INDAGAR"]


# --- Cuenta como turno de indagación -------------------------------------------------------------


def test_the_next_turn_counts_it_as_an_inquiry_turn() -> None:
    first = selecting(reporting(USEFUL, thread_action="nuevo"), "parcial", "E1.2")
    agent = ScriptedAgent(first, PARTIAL)
    retriever = FakeRetriever(clear_evidence())
    service = make_service(agent, InMemoryThreadRepository(), config=ACTIVE, retriever=retriever)

    service.send("tengo ardor")
    second = service.send("desde ayer")

    assert inquiry_of(second).turn == 2 and inquiry_of(second).progress is True


def base_inquiry(mode: TurnMode, **fields: Any) -> InquiryTrace:
    return InquiryTrace(mode, 0, 0, 0.7, 0.1, 2, "Acidez", None, False, applied=True, **fields)


def test_mode_after_answer_follows_the_table() -> None:
    policy, state = InquiryPolicy(), InquiryState()
    answering = base_inquiry(TurnMode.ANSWER)

    partial = mode_after_answer(answering, SelectionVerdict.PARTIAL, state, policy)
    full = mode_after_answer(answering, SelectionVerdict.ANSWERS, state, policy)

    assert (partial.mode, partial.turn) == (TurnMode.ANSWER_AND_INQUIRE, 1)
    assert full == answering


def test_an_exhausted_inquiry_does_not_ask_again() -> None:
    state = InquiryState(TurnMode.ANSWER_AND_INQUIRE, turn=3)
    answering = base_inquiry(TurnMode.ANSWER)

    final = mode_after_answer(answering, SelectionVerdict.PARTIAL, state, InquiryPolicy())

    assert final == answering


def test_answer_only_returns_the_counted_turn() -> None:
    state = InquiryState(TurnMode.INQUIRE, turn=1)
    inquiry = replace(base_inquiry(TurnMode.ANSWER_AND_INQUIRE), turn=2)

    assert answer_only(inquiry, state).turn == 1


def test_answering_while_inquiring_needs_a_record_that_orients() -> None:
    inquiring = base_inquiry(TurnMode.INQUIRE)

    assert answers_while_inquiring(inquiring)
    assert not answers_while_inquiring(replace(inquiring, has_answer=False))
    assert not answers_while_inquiring(replace(inquiring, applied=False))
    assert not answers_while_inquiring(None)


def test_the_verified_question_keeps_only_questions_up_to_the_limit() -> None:
    draft = ("Gracias por contarme.", "¿Desde cuándo?", "¿Te duele?")

    assert verified_question(draft, ["tengo ardor"], GroundingPolicy()) == "¿Desde cuándo?"
    assert verified_question(("Gracias.",), ["x"], GroundingPolicy()) == ""
