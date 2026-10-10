"""Pruebas del detector determinista de alarmas y de la política (dominio y aplicación)."""

from pathlib import Path

import pytest

from cardio_materno.application.alarm_policy import (
    ALARM_SIGNS_PLACEHOLDER,
    NO_SIGNS_TEXT,
    AlarmPolicy,
    compose_reply,
    render_system_prompt,
)
from cardio_materno.domain.alarms import (
    AlertOrigin,
    Severity,
    detect_alarms,
    most_severe,
    normalize_text,
)
from tests.unit.fakes import PRIORITY_MESSAGE, URGENT_MESSAGE, make_alarm_policy


def test_normalize_text_lowercases_and_removes_accents_and_extra_spaces() -> None:
    assert (
        normalize_text("  Visión   BORROSA, ¿qué hago? Niño ") == "vision borrosa, ¿que hago? nino"
    )


def test_patterns_match_regardless_of_accents_and_case() -> None:
    rules = make_alarm_policy().rules

    assert [r.id for r in detect_alarms(["Tengo la PRESIÓN ALTA"], rules)] == ["T-PRI"]


def test_several_rules_can_trigger_and_most_severe_wins() -> None:
    rules = detect_alarms(["presion alta y sangrado vaginal"], make_alarm_policy().rules)

    assert [r.id for r in rules] == ["T-URG", "T-PRI"]
    assert most_severe(rules).severity is Severity.IMMEDIATE


def test_empty_texts_trigger_nothing() -> None:
    assert detect_alarms(["", "   "], make_alarm_policy().rules) == []


def test_most_severe_requires_rules() -> None:
    with pytest.raises(ValueError):
        most_severe([])


def test_policy_returns_none_without_alarm_and_respects_exclusions() -> None:
    policy = make_alarm_policy()

    assert policy.evaluate(["tengo acidez"], AlertOrigin.USER) is None
    assert policy.evaluate(["presion alta"], AlertOrigin.AGENT, exclude={"T-PRI"}) is None


def test_policy_decision_carries_message_of_most_severe_rule() -> None:
    decision = make_alarm_policy().evaluate(["presion alta, sangrado vaginal"], AlertOrigin.USER)

    assert decision is not None
    assert decision.is_immediate
    assert decision.message == URGENT_MESSAGE
    assert decision.rule_ids == ("T-URG", "T-PRI")


def test_compose_reply_variants() -> None:
    policy = make_alarm_policy()
    urgent = policy.evaluate(["sangrado vaginal"], AlertOrigin.USER)
    priority = policy.evaluate(["presion alta"], AlertOrigin.USER)
    assert urgent is not None and priority is not None

    assert compose_reply([], "hola") == "hola"
    assert compose_reply([urgent], "hola") == URGENT_MESSAGE
    assert compose_reply([priority], "hola") == f"{PRIORITY_MESSAGE}\n\nhola"
    assert compose_reply([priority], None) == PRIORITY_MESSAGE
    with pytest.raises(ValueError):
        compose_reply([], None)


def test_rule_matches_its_own_sign_name_ignoring_accents_and_case() -> None:
    rule = make_alarm_policy().rules[0]

    assert rule.matches(normalize_text("SANGRADO VAGINAL en el embarazo de 7 meses"))


def test_render_system_prompt_inserts_unique_sign_names() -> None:
    template = f"Reglas.\n{ALARM_SIGNS_PLACEHOLDER}\nFin."

    prompt = render_system_prompt(template, make_alarm_policy())

    assert prompt == "Reglas.\n- Sangrado vaginal\n- Presión alta\nFin."


def test_render_system_prompt_without_rules_says_so() -> None:
    prompt = render_system_prompt(ALARM_SIGNS_PLACEHOLDER, AlarmPolicy((), {}))

    assert prompt == NO_SIGNS_TEXT


def test_current_system_prompt_has_the_signs_placeholder() -> None:
    prompts = Path(__file__).resolve().parents[2] / "src" / "cardio_materno" / "prompts"

    assert ALARM_SIGNS_PLACEHOLDER in (prompts / "analysis_prompt_v1.md").read_text(
        encoding="utf-8"
    )
