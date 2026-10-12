"""Pruebas de las funciones puras del script de comparación de modelos (B-022)."""

import pytest
from scripts.benchmark_models import (
    ComboResult,
    dropped_sentences,
    filter_two_via,
    outcome_kind,
    parse_combo,
    percentile,
    record_stage_times,
    render_row,
)

from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.trace import GroundingCheck, ReplyTrace, RetrievalStatus, StageTiming
from tests.unit.fakes import make_alarm_policy


def test_combo_with_one_model_uses_it_for_both_stages() -> None:
    assert parse_combo("qwen3:8b") == ("qwen3:8b", "qwen3:8b")
    assert parse_combo("qwen3:8b+mistral-small3.1:24b") == ("qwen3:8b", "mistral-small3.1:24b")


@pytest.mark.parametrize(
    ("trace", "kind"),
    [
        (None, "otro"),
        (ReplyTrace(), "otro"),
        (ReplyTrace(retrieval_status=RetrievalStatus.INSUFFICIENT), "abstención"),
        (
            ReplyTrace(retrieval_status=RetrievalStatus.SUFFICIENT, grounding=GroundingCheck(2, 2)),
            "verificada",
        ),
        (
            ReplyTrace(
                retrieval_status=RetrievalStatus.SUFFICIENT, grounding=GroundingCheck(0, 1, True)
            ),
            "literal",
        ),
    ],
    ids=["sin-traza", "sin-busqueda", "abstencion", "verificada", "literal"],
)
def test_outcome_kind(trace: ReplyTrace | None, kind: str) -> None:
    assert outcome_kind(trace) == kind


def test_percentile_uses_nearest_rank_and_handles_empty_lists() -> None:
    values = [5.0, 1.0, 3.0, 2.0, 4.0]

    assert percentile(values, 0.5) == 3.0
    assert percentile(values, 0.9) == 5.0
    assert percentile([], 0.5) is None


def test_reply_time_is_recorded_only_when_there_was_a_reply_call() -> None:
    result = ComboResult("a", "b")
    timings = (StageTiming("análisis", 2.0), StageTiming("respuesta", 7.5))

    record_stage_times(ReplyTrace(timings=timings), result)
    record_stage_times(None, result)

    assert result.reply_seconds == [7.5]


def test_report_row_summarizes_a_combination() -> None:
    result = ComboResult(
        "qwen3:8b",
        "mistral",
        json_errors=1,
        scope_hits=8,
        scope_total=9,
        alarm_hits=18,
        alarm_total=20,
        outcomes={"verificada": 10, "literal": 3, "abstención": 2, "otro": 1},
        turn_seconds=[10.0, 20.0],
        analysis_seconds=[3.0],
        reply_seconds=[],
    )

    assert render_row(result) == (
        "| qwen3:8b | mistral | 1 | 8/9 | 18/20 | 0/20 | 10 | 3 | 2 | 1 | "
        "20.0 s | 20.0 s | 3.0 s | — |"
    )


def test_dropped_sentences_come_from_the_grounding_check() -> None:
    check = GroundingCheck(1, 2, True, ("Toma manzanilla.",))

    assert dropped_sentences(ReplyTrace(grounding=check)) == ("Toma manzanilla.",)
    assert dropped_sentences(ReplyTrace()) == () and dropped_sentences(None) == ()


def test_filter_two_via_reports_text_and_code_paths() -> None:
    policy = make_alarm_policy()
    both = AnalysisTurn(
        ThreadAction.NEW,
        Domain.NONE,
        "s",
        ("sangrado vaginal",),
        reported_signs=("SANGRADO_VAGINAL",),
    )
    code_only = AnalysisTurn(
        ThreadAction.NEW, Domain.NONE, "s", reported_signs=("SANGRADO_VAGINAL",)
    )

    assert filter_two_via(policy, both, "T-URG") == ("texto", "código")
    assert filter_two_via(policy, code_only, "T-URG") == ("código",)
    assert filter_two_via(policy, code_only, "T-PRI") == ()
    assert filter_two_via(policy, None, "T-URG") == ()
