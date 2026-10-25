"""Pruebas del script de evaluación de la base v2 (MIG-08)."""

from collections import Counter

import pytest
from scripts.evaluate_kb_v2 import (
    ALARM_RULES_FILE,
    RetrievalTally,
    alarm_report,
    evaluate_alarms,
    parse_stages,
    percentiles,
    record_hit,
    retrieval_report,
)

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.domain.knowledge import Route, Stage
from tests.unit.fakes import case_entry, case_profile


def test_record_hit_counts_first_and_top_three_and_keeps_scores() -> None:
    tally = RetrievalTally()

    record_hit(tally, "a", [("a", 0.8), ("b", 0.6)])
    record_hit(tally, "a", [("b", 0.7), ("a", 0.6)])
    record_hit(tally, "a", [])

    assert (tally.total, tally.top1, tally.top3) == (3, 1, 2)
    assert tally.hit_scores == [0.8] and tally.miss_scores == [0.7]


def test_percentiles_of_scores() -> None:
    assert percentiles([]) == "sin datos"
    assert percentiles([0.1 * n for n in range(1, 11)]).startswith("p5 0.10")


def test_alarm_evaluation_flags_urgencies_in_self_care_cases() -> None:
    chest = case_entry("dolor_pared", Stage.DISCRIMINATORS)
    chest = chest.__class__(**{**chest.__dict__, "question": "me duele el pecho de cargar"})
    calm = case_entry("colico", Stage.DISCRIMINATORS)
    profiles = {"dolor_pared": case_profile("dolor_pared"), "colico": case_profile("colico")}

    tally = evaluate_alarms([chest, calm], profiles, load_alarm_policy(ALARM_RULES_FILE))

    assert tally.counts[str(Route.SELF_CARE)]["urgencia_inmediata"] == 1
    assert len(tally.examples) == 1 and "RN-CV-01" in tally.examples[0]
    assert "autocuidado (2)" in "\n".join(alarm_report(tally))


def test_retrieval_stages_default_to_opening_stages_and_reject_unknown_ones() -> None:
    assert parse_stages(["s", "recuperacion"]) == (Stage.DISCRIMINATORS, Stage.CASE_CHECK)
    assert parse_stages(["s", "recuperacion", "T3_contexto"]) == (Stage.CONTEXT,)
    with pytest.raises(ValueError):
        parse_stages(["s", "recuperacion", "T9"])


def test_retrieval_report_shows_the_stage_of_the_first_result() -> None:
    tally = RetrievalTally(first_stages=Counter({"T1_discriminantes": 3, "evolucion_leve": 1}))

    report = "\n".join(retrieval_report(tally, 0.5))

    assert "T1_discriminantes 3, evolucion_leve 1" in report
