"""Pruebas golden de las reglas de alarma contra el catálogo real (ADR 0007).

Las frases viven en `alarm_phrases.json` para que el equipo clínico pueda ampliarlas sin
tocar código. Toda regla del catálogo debe tener al menos 2 frases que la activen.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.domain.alarms import detect_alarms

pytestmark = pytest.mark.conversational

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG = load_alarm_policy(PROJECT_ROOT / "knowledge" / "alarm_rules.json")
PHRASES: dict[str, Any] = json.loads(
    (Path(__file__).parent / "alarm_phrases.json").read_text(encoding="utf-8")
)
MIN_POSITIVE_PHRASES = 2


def _cases(key: str) -> list[tuple[str, str]]:
    """Pares (regla, frase) de la lista indicada."""
    return [
        (rule_id, phrase)
        for rule_id, cases in PHRASES["rules"].items()
        for phrase in cases.get(key, [])
    ]


def _triggered(text: str) -> set[str]:
    """IDs de las reglas que activa un texto."""
    return {rule.id for rule in detect_alarms([text], CATALOG.rules)}


@pytest.mark.parametrize(("rule_id", "phrase"), _cases("debe_activar"))
def test_phrase_triggers_its_rule(rule_id: str, phrase: str) -> None:
    assert rule_id in _triggered(phrase)


@pytest.mark.parametrize(("rule_id", "phrase"), _cases("no_debe_activar"))
def test_phrase_does_not_trigger_rule(rule_id: str, phrase: str) -> None:
    assert rule_id not in _triggered(phrase)


@pytest.mark.parametrize("phrase", PHRASES["ninguna_regla"])
def test_everyday_phrases_trigger_no_rule(phrase: str) -> None:
    assert _triggered(phrase) == set()


def test_every_catalog_rule_has_enough_positive_phrases() -> None:
    for rule in CATALOG.rules:
        positives = PHRASES["rules"].get(rule.id, {}).get("debe_activar", [])
        assert len(positives) >= MIN_POSITIVE_PHRASES, f"{rule.id} sin frases suficientes"


def test_phrases_only_reference_existing_rules() -> None:
    catalog_ids = {rule.id for rule in CATALOG.rules}
    assert set(PHRASES["rules"]) <= catalog_ids


@pytest.mark.parametrize("rule", CATALOG.rules, ids=lambda rule: rule.id)
def test_rule_triggers_with_its_own_sign_name_as_the_agent_would_report_it(rule: Any) -> None:
    reported = f"{rule.sign}: contexto adicional del caso"

    assert rule.id in _triggered(reported)
