"""Pruebas del detector determinista de alarmas y de la política (dominio y aplicación)."""

from pathlib import Path

import pytest

from cardio_materno.application.alarm_policy import (
    ALARM_SIGNS_PLACEHOLDER,
    NO_SIGNS_TEXT,
    REMINDER_MESSAGES,
    AlarmPolicy,
    compose_reply,
    reminder_for,
    render_system_prompt,
)
from cardio_materno.bootstrap.main import ANALYSIS_PROMPT_FILE
from cardio_materno.domain.alarms import (
    AlertOrigin,
    Severity,
    detect_alarms,
    most_severe,
    normalize_text,
    rules_for_codes,
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

    assert prompt == (
        "Reglas.\n- SANGRADO_VAGINAL: Sangrado vaginal (ej.: me sangra)\n"
        "- PRESION_ALTA: Presión alta\nFin."
    )


def test_render_system_prompt_without_rules_says_so() -> None:
    prompt = render_system_prompt(ALARM_SIGNS_PLACEHOLDER, AlarmPolicy((), {}))

    assert prompt == NO_SIGNS_TEXT


def test_current_system_prompt_has_the_signs_placeholder() -> None:
    prompts = Path(__file__).resolve().parents[2] / "src" / "cardio_materno" / "prompts"

    assert ALARM_SIGNS_PLACEHOLDER in (prompts / ANALYSIS_PROMPT_FILE.name).read_text(
        encoding="utf-8"
    )


def test_rules_for_codes_is_an_exact_match_in_catalog_order() -> None:
    rules = make_alarm_policy().rules

    assert [r.id for r in rules_for_codes(["PRESION_ALTA", "SANGRADO_VAGINAL"], rules)] == [
        "T-URG",
        "T-PRI",
    ]
    assert rules_for_codes(["sangrado_vaginal", "OTRO"], rules) == []


def test_policy_evaluates_codes_with_agent_code_origin_and_exclusions() -> None:
    policy = make_alarm_policy()

    decision = policy.evaluate_codes(["SANGRADO_VAGINAL"])

    assert decision is not None and decision.origin is AlertOrigin.AGENT_CODE
    assert decision.rule_ids == ("T-URG",) and decision.message == URGENT_MESSAGE
    assert policy.evaluate_codes(["SANGRADO_VAGINAL"], exclude={"T-URG"}) is None
    assert policy.evaluate_codes([]) is None
    assert policy.codes == ("SANGRADO_VAGINAL", "PRESION_ALTA")


# --- Alarmas ya avisadas (ADR 0018) --------------------------------------------------------


def test_split_alerted_keeps_new_rules_and_returns_the_reminded_ones() -> None:
    policy = make_alarm_policy()
    found = policy.evaluate_codes(["SANGRADO_VAGINAL", "PRESION_ALTA"])
    assert found is not None

    fresh, reminded = policy.split_alerted([found], {"T-URG"})

    assert [d.rule_ids for d in fresh] == [("T-PRI",)]
    assert fresh[0].message == PRIORITY_MESSAGE and fresh[0].origin is AlertOrigin.AGENT_CODE
    assert [rule.id for rule in reminded] == ["T-URG"]


def test_split_alerted_drops_a_decision_whose_rules_were_all_alerted() -> None:
    policy = make_alarm_policy()
    found = policy.evaluate_codes(["SANGRADO_VAGINAL"])
    assert found is not None

    assert policy.split_alerted([found], {"T-URG"})[0] == ()


def test_reminder_text_follows_the_severity_of_the_reminded_rules() -> None:
    policy = make_alarm_policy()
    urgent = policy.evaluate_codes(["SANGRADO_VAGINAL"])
    priority = policy.evaluate_codes(["PRESION_ALTA"])
    assert urgent is not None and priority is not None

    assert reminder_for(urgent.rules, ()) == REMINDER_MESSAGES[Severity.IMMEDIATE]
    assert reminder_for(priority.rules, ()) == REMINDER_MESSAGES[Severity.PRIORITY]
    assert reminder_for((), ()) is None


def test_no_reminder_when_a_new_alarm_as_severe_is_shown() -> None:
    policy = make_alarm_policy()
    urgent = policy.evaluate_codes(["SANGRADO_VAGINAL"])
    priority = policy.evaluate_codes(["PRESION_ALTA"])
    assert urgent is not None and priority is not None

    assert reminder_for(priority.rules, [urgent]) is None
    assert reminder_for(urgent.rules, [priority]) == REMINDER_MESSAGES[Severity.IMMEDIATE]
