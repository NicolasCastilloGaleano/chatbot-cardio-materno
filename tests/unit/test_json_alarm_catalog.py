"""Pruebas del cargador y validador del catálogo de alarmas."""

import json
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import (
    AlarmCatalogError,
    load_alarm_policy,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def valid_rule(**overrides: Any) -> dict[str, Any]:
    rule = {
        "id": "RN-X-01",
        "code": "DOLOR_PECHO",
        "domain": "cardiovascular",
        "population": "adulto",
        "sign": "Dolor en el pecho",
        "severity": "urgencia_inmediata",
        "patterns": [r"dolor (en el|del) pecho"],
        "message_id": "urg",
        "source": "prueba",
    }
    return rule | overrides


def write_catalog(tmp_path: Path, rules: list[Any], messages: Any = None) -> Path:
    path = tmp_path / "rules.json"
    data = {"messages": messages if messages is not None else {"urg": "Ve a urgencias"}}
    path.write_text(json.dumps(data | {"rules": rules}), encoding="utf-8")
    return path


def test_real_catalog_loads_with_unique_ids_and_codes() -> None:
    policy = load_alarm_policy(PROJECT_ROOT / "knowledge" / "alarm_rules.json")

    ids = [rule.id for rule in policy.rules]
    assert len(ids) == len(set(ids)) > 0
    assert len(policy.codes) == len(policy.rules)
    assert all(len(rule.examples) >= 2 for rule in policy.rules)


def test_valid_catalog_builds_policy(tmp_path: Path) -> None:
    policy = load_alarm_policy(write_catalog(tmp_path, [valid_rule()]))

    assert policy.rules[0].id == "RN-X-01"
    assert policy.rules[0].matches("dolor del pecho")
    assert (policy.rules[0].code, policy.rules[0].examples) == ("DOLOR_PECHO", ())


@pytest.mark.parametrize(
    ("rules", "expected"),
    [
        ([valid_rule(), valid_rule()], "IDs de regla repetidos"),
        ([valid_rule(), valid_rule(id="RN-X-02")], "Códigos de signo repetidos"),
        ([valid_rule(code="dolor pecho")], "'code'"),
        ([valid_rule(examples="me duele")], "'examples'"),
        ([valid_rule(severity="grave")], "severity"),
        ([valid_rule(domain="oncologia")], "domain"),
        ([valid_rule(patterns=["(sin cerrar"])], "patrón inválido"),
        ([valid_rule(patterns=[])], "patterns"),
        ([valid_rule(message_id="otro")], "message_id"),
        ([{"id": "RN-X-02"}], "incompleta"),
        ([], "rules"),
    ],
)
def test_invalid_catalog_raises_clear_error(
    tmp_path: Path, rules: list[Any], expected: str
) -> None:
    with pytest.raises(AlarmCatalogError, match=expected):
        load_alarm_policy(write_catalog(tmp_path, rules))


def test_missing_messages_raise_error(tmp_path: Path) -> None:
    with pytest.raises(AlarmCatalogError, match="messages"):
        load_alarm_policy(write_catalog(tmp_path, [valid_rule()], messages={}))


def test_missing_or_broken_file_raises_error(tmp_path: Path) -> None:
    with pytest.raises(AlarmCatalogError, match="No existe"):
        load_alarm_policy(tmp_path / "no-existe.json")
    broken = tmp_path / "roto.json"
    broken.write_text("{no es json", encoding="utf-8")
    with pytest.raises(AlarmCatalogError, match="JSON"):
        load_alarm_policy(broken)
