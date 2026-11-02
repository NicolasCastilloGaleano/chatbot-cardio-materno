"""Pruebas del selector de evidencia en modo activo (HU-13, ADR 0019, paso 1.2)."""

from dataclasses import replace
from typing import Any

from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence_selection import (
    Selection,
    SelectionActivation,
    selected_evidence,
    selection_trace,
    visible_ids,
)
from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    LITERAL_TEMPLATE,
    GroundedReply,
    with_selected_literal,
)
from cardio_materno.application.inquiry_policy import (
    InquiryActivation,
    InquiryPolicy,
    InquiryState,
    mode_without_answer,
)
from cardio_materno.domain.knowledge import EvidenceItem, RetrievalResult
from cardio_materno.domain.trace import (
    GroundingCheck,
    InquiryTrace,
    OfferedSentence,
    RecordFit,
    RecordReview,
    SelectionTrace,
    SelectionVerdict,
    TurnMode,
)
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    FakeRetriever,
    ScriptedAgent,
    agent_json,
    evidence_result,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    selecting,
)
from tests.unit.test_inquiry_observation import inquiry_of, reporting

REFLUX = "El reflujo causa ardor. Evita las comidas pesadas."
USEFUL = "Evita las comidas pesadas."
ACTIVE: dict[str, Any] = {
    "selection_activation": SelectionActivation.ACTIVE,
    "selection_prompt": "SELECTOR",
    "selected_reply_prompt": "REDACTOR",
    "inquiry_activation": InquiryActivation.ACTIVE,
    "inquiry_prompt": "INDAGAR",
}


def clear_evidence(answer: str = REFLUX) -> RetrievalResult:
    """Evidencia clara para la regla: responde con un registro *Solucionar*."""
    found = evidence_result(knowledge_entry(answer=answer))
    entry = found.items[0].entry
    candidates = (EvidenceItem("C1", entry, 0.74), EvidenceItem("C2", entry, 0.73))
    return replace(found, candidates=candidates, best_score=0.74)


def send(turn: dict[str, Any], text: str = "tengo ardor", **config: Any) -> tuple[TurnResult, Any]:
    agent = ScriptedAgent(turn)
    service = make_service(agent, config=ACTIVE | config, retriever=FakeRetriever(clear_evidence()))
    return service.send(text), agent


def selection_of(result: TurnResult) -> SelectionTrace:
    assert result.trace is not None and result.trace.selection is not None
    return result.trace.selection


# --- La respuesta sale de las frases visibles ------------------------------------------------


def test_the_reply_comes_only_from_the_selected_sentences() -> None:
    result, agent = send(selecting(reporting(USEFUL), "responde", "E1.2"))

    assert result.reply == USEFUL
    assert selection_of(result).applied and selection_of(result).shown == ("E1.2",)
    prompts = [call[0].content for call in agent.responder.calls]
    assert prompts == ["SELECTOR", "REDACTOR"]
    context = "\n".join(message.content for message in agent.responder.calls[1])
    assert USEFUL in context and "El reflujo causa ardor" not in context


def test_a_sentence_that_was_not_selected_gives_no_support() -> None:
    turn = selecting(reporting("El reflujo causa ardor."), "responde", "E1.2")

    result, _ = send(turn)

    assert result.reply == LITERAL_TEMPLATE.format(answer=USEFUL)
    assert result.trace is not None and result.trace.grounding is not None
    assert result.trace.grounding.literal
    assert result.trace.grounding.literal_shown == 1


def test_if_the_selector_fails_the_turn_follows_the_previous_flow() -> None:
    turn = selecting(reporting(REFLUX), "responde", "E1.2")

    result, agent = send(turn | {"selection": LanguageModelError("sin modelo")})

    assert result.reply == REFLUX
    assert selection_of(result).verdict is None and not selection_of(result).applied
    assert [call[0].content for call in agent.responder.calls] == ["SELECTOR", "REPLY"]


def test_observing_does_not_use_the_selected_sentences() -> None:
    config = {"selection_activation": SelectionActivation.OBSERVE}
    turn = selecting(reporting(REFLUX), "responde", "E1.2")

    result, agent = send(turn, **config)

    assert result.reply == REFLUX
    assert selection_of(result).shown == ("E1.2",) and not selection_of(result).applied
    assert agent.responder.calls[1][0].content == "REPLY"


# --- Sin frases visibles -----------------------------------------------------------------------


def test_a_partial_record_is_not_shown_and_the_rule_inquires() -> None:
    turn = selecting(reporting("x"), "parcial", "E1.2", fit="en_parte")

    result, agent = send(turn)

    inquiry = inquiry_of(result)
    assert (inquiry.mode, inquiry.rule_mode, inquiry.turn) == (TurnMode.INQUIRE, TurnMode.ANSWER, 1)
    assert selection_of(result).shown == () and selection_of(result).applied
    assert result.trace is not None and result.trace.evidence == ()
    assert agent.responder.calls[1][0].content == "INDAGAR"


def test_no_answer_to_an_information_question_abstains() -> None:
    result, _ = send(selecting(agent_json("x"), "no_responde"))

    assert result.reply == ABSTENTION_TEXT
    assert inquiry_of(result).mode is TurnMode.ABSTAIN


def test_without_the_inquiry_rule_no_answer_abstains() -> None:
    config = {"inquiry_activation": InquiryActivation.OFF}

    result, _ = send(selecting(reporting("x"), "no_responde"), **config)

    assert result.reply == ABSTENTION_TEXT


def test_a_priority_alarm_is_shown_alone_if_nothing_is_visible() -> None:
    turn = selecting(reporting("x"), "parcial", "E1.2", fit="en_parte")

    result, _ = send(turn, "tengo presion alta", alarm_policy=make_alarm_policy())

    assert result.reply == PRIORITY_MESSAGE


def test_a_priority_alarm_goes_with_the_visible_sentences() -> None:
    turn = selecting(reporting(USEFUL), "responde", "E1.2")

    result, _ = send(turn, "tengo presion alta", alarm_policy=make_alarm_policy())

    assert PRIORITY_MESSAGE in result.reply and USEFUL in result.reply


# --- Reglas puras ------------------------------------------------------------------------------


OFFERED = (
    OfferedSentence("E1.1", "Evita las comidas pesadas."),
    OfferedSentence("E1.2", "Acude a urgencias si empeora."),
    OfferedSentence("E2.1", "Pide ayuda para el traslado."),
    OfferedSentence("E2.2", "Llama al 123."),
)
MIXED = Selection(
    SelectionVerdict.PARTIAL,
    ("E1.1", "E2.1"),
    (RecordReview("E1", RecordFit.YES), RecordReview("E2", RecordFit.PARTLY, "cifra")),
)


def test_only_si_records_are_visible_and_reinforced() -> None:
    assert visible_ids(MIXED, OFFERED, urgent=False) == ("E1.1", "E1.2")


def test_a_partial_record_is_visible_only_during_an_urgency_without_reinforcing() -> None:
    assert visible_ids(MIXED, OFFERED, urgent=True) == ("E1.1", "E2.1", "E1.2")


def test_a_record_without_review_is_not_visible() -> None:
    selection = Selection(SelectionVerdict.ANSWERS, ("E1.1",))

    assert visible_ids(selection, OFFERED, urgent=False) == ()


def test_selected_evidence_drops_the_rest_of_the_entry_and_its_question() -> None:
    found = evidence_result(knowledge_entry(answer=REFLUX))
    trace = replace(selection_trace(MIXED, OFFERED, False), shown=("E1.1",))

    reduced = selected_evidence(found, trace)

    assert reduced.items[0].entry.answer == USEFUL
    assert reduced.items[0].entry.question == ""


def test_the_selected_literal_only_replaces_a_failed_draft() -> None:
    verified = GroundedReply("Redacción.", ("E1",), GroundingCheck(1, 1))
    failed = GroundedReply("Otro texto.", ("E1",), GroundingCheck(0, 1, True))

    assert with_selected_literal(verified, ["Frase."]) is verified
    assert with_selected_literal(failed, ["Frase."]).text == LITERAL_TEMPLATE.format(
        answer="Frase."
    )


def test_without_an_answer_a_direct_request_or_an_exhausted_inquiry_ends_it() -> None:
    policy = InquiryPolicy()
    answer = InquiryTrace(TurnMode.ANSWER)
    inquiring = InquiryState(TurnMode.INQUIRE, turn=policy.max_turns)

    direct = mode_without_answer(replace(answer, wants_guidance=True), InquiryState(), policy)
    exhausted = mode_without_answer(answer, inquiring, policy)
    follows = mode_without_answer(answer, InquiryState(TurnMode.INQUIRE, turn=1), policy)

    assert direct.mode is TurnMode.ABSTAIN
    assert exhausted.mode is TurnMode.CLOSE
    assert (follows.mode, follows.turn) == (TurnMode.INQUIRE, 2)
