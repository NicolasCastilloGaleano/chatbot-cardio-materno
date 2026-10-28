"""Pruebas de la regla determinista de indagación (HU-11, ADR 0017)."""

from dataclasses import replace

import pytest

from cardio_materno.application.inquiry_policy import (
    InquiryPolicy,
    InquirySignals,
    InquiryState,
    evaluate_inquiry,
    previous_state,
    search_signals,
)
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import EvidenceItem
from cardio_materno.domain.trace import InquiryTrace, ReplyTrace, TurnMode
from tests.unit.fakes import knowledge_entry

POLICY = InquiryPolicy()
NO_STATE = InquiryState()
INQUIRING = InquiryState(TurnMode.INQUIRE, turn=1, best_score=0.50, top_category="Acidez")


def candidate(label: str, category: str, score: float) -> EvidenceItem:
    return EvidenceItem(label, replace(knowledge_entry(label), category=category), score)


def signals(
    best: float, margin: float = 0.0, agreement: int = 1, category: str = "Acidez"
) -> InquirySignals:
    return InquirySignals(best, margin, agreement, category)


def mode_of(
    sig: InquirySignals, state: InquiryState = NO_STATE, guidance: bool = False
) -> InquiryTrace:
    return evaluate_inquiry(sig, state, guidance, POLICY, applied=False)


# --- Señales -------------------------------------------------------------------------------


def test_signals_use_the_first_two_candidates_and_the_first_category() -> None:
    candidates = [
        candidate("C1", "Acidez", 0.58),
        candidate("C2", "Acidez", 0.55),
        candidate("C3", "Presión", 0.50),
    ]

    assert search_signals(candidates, 0.58) == InquirySignals(0.58, 0.03, 2, "Acidez")


def test_signals_without_candidates_keep_the_best_score() -> None:
    assert search_signals([], 0.32) == InquirySignals(0.32, 0.32, 0, "")


# --- Regla -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sig", "expected"),
    [
        (signals(0.70, margin=0.05), TurnMode.ANSWER),
        (signals(0.70, margin=0.01, agreement=2), TurnMode.ANSWER),
        (signals(0.70, margin=0.01, agreement=1), TurnMode.INQUIRE),
        (signals(0.66, margin=0.06, agreement=2), TurnMode.INQUIRE),
        (signals(0.55), TurnMode.INQUIRE),
        (signals(0.42), TurnMode.INQUIRE),
        (signals(0.30), TurnMode.ABSTAIN),
    ],
    ids=[
        "clara-margen",
        "clara-coincidencia",
        "alta-ambigua",
        "brazo-0,66",
        "prometedora",
        "piso",
        "nada",
    ],
)
def test_first_turn_of_a_topic(sig: InquirySignals, expected: TurnMode) -> None:
    result = mode_of(sig)

    assert result.mode is expected
    assert result.turn == (1 if expected is TurnMode.INQUIRE else 0)
    assert result.progress is None


def test_inquiry_with_progress_continues_and_counts_turns() -> None:
    result = mode_of(signals(0.52, category="Acidez"), INQUIRING)

    assert (result.mode, result.turn, result.stalled, result.progress) == (
        TurnMode.INQUIRE,
        2,
        0,
        True,
    )


def test_inquiry_answers_when_evidence_becomes_clear() -> None:
    result = mode_of(signals(0.70, margin=0.06), INQUIRING)

    assert (result.mode, result.turn) == (TurnMode.ANSWER, 1)


@pytest.mark.parametrize(("best", "expected"), [(0.55, TurnMode.ANSWER), (0.45, TurnMode.CLOSE)])
def test_max_inquiry_turns_force_an_answer_or_a_close(best: float, expected: TurnMode) -> None:
    exhausted = InquiryState(TurnMode.INQUIRE, turn=3, best_score=0.50, top_category="Acidez")

    assert mode_of(signals(best), exhausted).mode is expected


def test_two_inquiry_turns_without_progress_stop_the_inquiry() -> None:
    stuck = InquiryState(TurnMode.INQUIRE, turn=2, stalled=1, best_score=0.48, top_category="A")

    result = mode_of(signals(0.47, category="B"), stuck)

    assert (result.mode, result.stalled, result.progress) == (TurnMode.CLOSE, 2, False)


def test_direct_request_answers_with_enough_evidence() -> None:
    assert mode_of(signals(0.52), guidance=True).mode is TurnMode.ANSWER


def test_direct_request_during_an_inquiry_without_evidence_closes() -> None:
    assert mode_of(signals(0.45, category="Otra"), INQUIRING, guidance=True).mode is TurnMode.CLOSE


def test_direct_request_without_inquiry_and_without_evidence_follows_the_table() -> None:
    assert mode_of(signals(0.30), guidance=True).mode is TurnMode.ABSTAIN


def test_after_asking_for_details_nothing_close_ends_with_a_close() -> None:
    asked = InquiryState(TurnMode.ABSTAIN, best_score=0.30)

    assert mode_of(signals(0.32), asked).mode is TurnMode.CLOSE


def test_an_answer_resets_the_inquiry_turns() -> None:
    answered = InquiryState(TurnMode.ANSWER, turn=2, best_score=0.62, top_category="Acidez")

    result = mode_of(signals(0.55), answered)

    assert (result.mode, result.turn, result.progress) == (TurnMode.INQUIRE, 1, None)


def test_applied_flag_and_wants_guidance_are_recorded() -> None:
    result = evaluate_inquiry(signals(0.55), InquiryState(), True, POLICY, applied=True)

    assert result.applied and result.wants_guidance


# --- Estado desde el hilo --------------------------------------------------------------------


def test_previous_state_comes_from_the_last_assistant_trace() -> None:
    inquiry = InquiryTrace(TurnMode.INQUIRE, turn=2, stalled=1, best_score=0.5, top_category="A")
    recent = (
        ChatMessage(Role.ASSISTANT, "antes", trace=ReplyTrace()),
        ChatMessage(Role.USER, "x"),
        ChatMessage(Role.ASSISTANT, "¿Desde cuándo?", trace=ReplyTrace(inquiry=inquiry)),
        ChatMessage(Role.USER, "desde ayer"),
    )

    assert previous_state(recent) == InquiryState(TurnMode.INQUIRE, 2, 1, 0.5, "A")


def test_without_an_inquiry_trace_the_state_is_empty() -> None:
    recent = (ChatMessage(Role.ASSISTANT, "hola", trace=ReplyTrace()),)

    assert previous_state(recent) == InquiryState()
    assert previous_state(()) == InquiryState()
