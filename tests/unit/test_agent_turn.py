"""Pruebas de la validación de la respuesta estructurada del agente."""

from typing import Any

import pytest

from cardio_materno.application.agent_turn import (
    AGENT_TURN_SCHEMA,
    ThreadAction,
    parse_agent_turn,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import Domain
from tests.unit.fakes import agent_json


def test_valid_json_is_parsed_and_trimmed() -> None:
    turn = parse_agent_turn(agent_json(reply="  Hola  ", thread_action="nuevo"))

    assert turn.reply == "Hola"
    assert turn.thread_action is ThreadAction.NEW
    assert turn.domain is Domain.MATERNAL_CHILD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("thread_action", "cerrar"),
        ("domain", "oncologia"),
        ("summary", "   "),
        ("reply", ""),
        ("reply", 42),
    ],
)
def test_invalid_values_raise_error(field: str, value: Any) -> None:
    data = agent_json() | {field: value}

    with pytest.raises(LanguageModelError, match=field):
        parse_agent_turn(data)


def test_missing_field_raises_error() -> None:
    data = agent_json()
    del data["summary"]

    with pytest.raises(LanguageModelError, match="summary"):
        parse_agent_turn(data)


def test_schema_lists_allowed_values() -> None:
    properties = AGENT_TURN_SCHEMA["properties"]

    assert properties["thread_action"]["enum"] == ["continuar", "nuevo"]
    assert properties["domain"]["enum"] == ["materno_infantil", "cardiovascular", "ninguno"]
    assert set(AGENT_TURN_SCHEMA["required"]) == {"thread_action", "domain", "summary", "reply"}
