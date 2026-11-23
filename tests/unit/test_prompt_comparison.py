"""Comparación v8/v9 del prompt de análisis: casos, calificación y resumen, sin Ollama.

Prueba la herramienta, no al modelo: un analizador guionizado no dice nada de cómo se
comporta el agente real. Los resultados reales salen de `scripts/compare_analysis_prompts.py`.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from scripts.compare_analysis_prompts import Bench, Variant, run_comparison
from scripts.prompt_comparison import (
    ALARM,
    ALARM_MODEL,
    ALL,
    CAT_ALARM,
    CAT_ALARM_BARRIER,
    FACTS,
    NO_FACTS,
    NO_FALSE_ALARM,
    RETRIEVAL,
    V8,
    V9,
    Case,
    Observation,
    grade,
    load_cases,
    render_report,
    sign_test,
    summarize,
)

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    load_care_access_catalog,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.bootstrap.main import analysis_prompt
from cardio_materno.domain.conversation import ChatMessage
from cardio_materno.domain.trace import ModelUsage
from tests.unit.fakes import agent_json, make_alarm_policy, signing

REPO = Path(__file__).resolve().parents[2]
LIVE_DIR = REPO / "tests" / "live"
ALARM_PHRASES = REPO / "tests" / "conversational" / "alarm_phrases.json"


@pytest.fixture(scope="module")
def cases() -> list[Case]:
    return load_cases(LIVE_DIR, ALARM_PHRASES)


class GuidedAnalyzer:
    """Analizador guionizado: responde según la variante del prompt que recibe."""

    def __init__(self, by_variant: dict[str, list[dict[str, Any] | Exception]]) -> None:
        self._by_variant = {name: list(turns) for name, turns in by_variant.items()}
        self.schemas: list[dict[str, Any]] = []

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.schemas.append(schema)
        turn = self._by_variant[messages[0].content].pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn

    def last_usage(self) -> ModelUsage | None:
        return None


# --- El conjunto de casos -------------------------------------------------------------------


def test_the_case_set_is_built_from_the_existing_batteries(cases: list[Case]) -> None:
    by_category: dict[str, int] = {}
    for case in cases:
        by_category[case.category] = by_category.get(case.category, 0) + 1

    assert len({case.id for case in cases}) == len(cases) > 100
    assert by_category[CAT_ALARM] == by_category[CAT_ALARM_BARRIER] == 18
    assert by_category["adversarial"] >= 10 and by_category["continuidad"] >= 3


def test_every_expectation_points_to_something_that_exists(cases: list[Case]) -> None:
    policy = load_alarm_policy(REPO / "knowledge" / "alarm_rules.json")
    catalog = load_care_access_catalog(REPO / "knowledge" / "care_access.json")
    rules = {rule.id for rule in policy.rules}

    assert {case.rule for case in cases if case.rule} <= rules
    assert {code for case in cases for code in (*case.facts, *case.no_facts)} <= set(catalog.codes)


def test_adding_a_barrier_never_changes_the_expected_alarm(cases: list[Case]) -> None:
    by_id = {case.id: case for case in cases}
    paired = [case for case in cases if case.id.endswith("-b")]

    assert paired
    for case in paired:
        plain = by_id[case.id.removesuffix("-b")]
        assert case.message.startswith(plain.message)
        assert (case.rule, case.no_alarm, case.scope, case.categories) == (
            plain.rule,
            plain.no_alarm,
            plain.scope,
            plain.categories,
        )


# --- Calificación ---------------------------------------------------------------------------


def test_an_alarm_counts_if_either_filter_catches_it() -> None:
    case = Case("c", CAT_ALARM, "x", rule="RN-1")

    by_user = grade(case, Observation("c", V8, 0, rules_user=("RN-1",)))
    by_model = grade(case, Observation("c", V8, 0, rules_agent=("RN-1",)))
    missed = grade(case, Observation("c", V8, 0, rules_agent=("RN-2",)))

    assert by_user == {ALARM: True, ALARM_MODEL: False}
    assert by_model == {ALARM: True, ALARM_MODEL: True}
    assert missed == {ALARM: False, ALARM_MODEL: False}


def test_a_failed_call_fails_every_criterion_that_applies() -> None:
    case = Case("c", "x", "x", rule="RN-1", scope="en_alcance")

    graded = grade(case, Observation("c", V9, 0, error="sin respuesta", rules_user=("RN-1",)))

    assert graded and not any(graded.values())


def test_access_facts_are_only_graded_for_v9() -> None:
    case = Case("c", "x", "x", no_alarm=True, facts=("A",), no_facts=("B",))

    assert grade(case, Observation("c", V8, 0)) == {NO_FALSE_ALARM: True}
    assert grade(case, Observation("c", V9, 0, access_facts=("A", "B"))) == {
        NO_FALSE_ALARM: True,
        FACTS: True,
        NO_FACTS: False,
    }


def test_retrieval_is_graded_only_when_it_was_searched() -> None:
    case = Case("c", "x", "x", categories=("Presión",))
    found = Observation("c", V8, 0, retrieved=("r1",), retrieved_categories=("Presión",))

    assert grade(case, Observation("c", V8, 0)) == {}
    assert grade(case, found)[RETRIEVAL] is True


# --- Resumen --------------------------------------------------------------------------------


def observations(
    variant: str, detected: Sequence[bool], scope: str = "en_alcance"
) -> list[Observation]:
    return [
        Observation("c", variant, run, rules_agent=("RN-1",) if hit else (), scope=scope)
        for run, hit in enumerate(detected)
    ]


def test_a_regression_shows_as_a_discordant_case_with_its_noise_floor() -> None:
    case = Case("c", CAT_ALARM, "x", rule="RN-1")
    seen = [*observations(V8, [True, True, True]), *observations(V9, [True, False, False])]

    summary = summarize([case], seen)

    assert summary["resultados"][V8][ALL][ALARM] == [3, 3]
    assert summary["resultados"][V9][ALL][ALARM] == [1, 3]
    assert summary["discordantes"] == {V8: ["c"], V9: []}
    assert summary["acuerdo"]["v8~v9"]["rules_agent"] == [1, 3]
    assert summary["acuerdo"]["v8~v8"]["rules_agent"] == [2, 2]
    assert summary["acuerdo"]["v9~v9"]["rules_agent"] == [1, 2]


def test_one_discordant_case_is_not_evidence_either_way() -> None:
    assert sign_test(0, 0) == 1.0
    assert sign_test(1, 0) == 1.0
    assert sign_test(6, 0) == pytest.approx(0.03125)


def test_the_report_states_what_was_compared_and_what_was_missed() -> None:
    case = Case("c", CAT_ALARM, "x", rule="RN-1")
    seen = [*observations(V8, [True, True]), *observations(V9, [False, False])]

    report = render_report(summarize([case], seen), ["- Modelo de análisis: `modelo-de-prueba`"])

    assert "modelo-de-prueba" in report
    assert "| alarma coloquial | alarma detectada | 2/2 (100 %) | 0/2 (0 %) |" in report
    assert "`c`: v8 2/2 (100 %) · v9 0/2 (0 %)" in report
    assert "no demuestra equivalencia" in report


# --- Corrida con un analizador guionizado ---------------------------------------------------


def test_both_variants_get_the_same_case_and_only_v9_gets_the_access_schema() -> None:
    policy = make_alarm_policy()
    catalog = load_care_access_catalog(REPO / "knowledge" / "care_access.json")
    marked = signing(agent_json("x"), "SANGRADO_VAGINAL")
    analyzer = GuidedAnalyzer(
        {
            "P8": [marked, LanguageModelError("sin respuesta")],
            "P9": [marked | {"access_facts": ["SIN_AFILIACION", "NO_EXISTE"]}, agent_json("x")],
        }
    )
    variants = (Variant(V8, "P8"), Variant(V9, "P9", catalog.codes))
    cases = [
        Case("a", "x", "me sale algo por abajo y no tengo eps", facts=("SIN_AFILIACION",)),
        Case("b", "x", "mi cédula es 1.000.000.001, tengo sangrado vaginal"),
    ]

    seen = run_comparison(Bench(analyzer, policy), variants, cases, runs=1)

    by_key = {(item.case_id, item.variant): item for item in seen}
    assert len(seen) == 4
    assert by_key[("a", V8)].rules_agent == by_key[("a", V9)].rules_agent != ()
    assert by_key[("a", V8)].access_facts == ()
    assert by_key[("a", V9)].access_facts == ("SIN_AFILIACION",)
    assert by_key[("b", V8)].error and by_key[("b", V8)].rules_user == by_key[("b", V9)].rules_user
    assert by_key[("b", V9)].rules_user != ()
    with_facts = [schema for schema in analyzer.schemas if "access_facts" in schema["properties"]]
    assert len(with_facts) == 2 and len(analyzer.schemas) == 4


def test_v9_only_adds_to_v8_what_the_catalog_defines() -> None:
    policy = load_alarm_policy(REPO / "knowledge" / "alarm_rules.json")
    catalog = load_care_access_catalog(REPO / "knowledge" / "care_access.json")

    v8, v9 = analysis_prompt(policy, None), analysis_prompt(policy, catalog)

    # Medida usada en el ADR 0023 para estimar el riesgo de llenar la ventana de contexto.
    assert 3000 < len(v9) - len(v8) < 4500
    assert all(code in v9 and code not in v8 for code in catalog.codes)
