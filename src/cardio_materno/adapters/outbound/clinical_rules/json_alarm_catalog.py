"""Carga y valida el catálogo de alarmas `knowledge/alarm_rules.json` (ADR 0007).

El catálogo es contenido clínico versionado como datos: lo revisa y valida el equipo
clínico sin necesidad de leer código. Si el archivo tiene errores, el programa no
arranca (falla rápido) para no operar con reglas incompletas.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.domain.alarms import AlarmRule, Severity, compile_pattern
from cardio_materno.domain.conversation import Domain

RULE_FIELDS = (
    "id",
    "code",
    "domain",
    "population",
    "sign",
    "severity",
    "patterns",
    "message_id",
)
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class AlarmCatalogError(ValueError):
    """El catálogo de alarmas no existe o tiene un error de formato o contenido."""


def load_alarm_policy(path: Path) -> AlarmPolicy:
    """Lee el catálogo, valida cada regla y construye la política de alarmas.

    Args:
        path: Ruta del archivo JSON del catálogo.

    Returns:
        La política con las reglas compiladas y los mensajes fijos.

    Raises:
        AlarmCatalogError: Si el archivo no existe, no es JSON o alguna regla es inválida.
    """
    data = _read_json(path)
    messages = _parse_messages(data.get("messages"))
    rules = [_parse_rule(item, messages) for item in _rule_items(data)]
    _check_unique("IDs de regla", [rule.id for rule in rules])
    _check_unique("Códigos de signo", [rule.code for rule in rules])
    return AlarmPolicy(rules, messages)


def _read_json(path: Path) -> dict[str, Any]:
    """Lee el archivo y verifica que sea un objeto JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AlarmCatalogError(f"No existe el catálogo de alarmas: {path}") from error
    except json.JSONDecodeError as error:
        raise AlarmCatalogError(f"El catálogo de alarmas no es JSON válido: {error}") from error
    if not isinstance(data, dict):
        raise AlarmCatalogError("El catálogo de alarmas debe ser un objeto JSON")
    return data


def _parse_messages(raw: Any) -> dict[str, str]:
    """Valida el diccionario de mensajes fijos."""
    if not isinstance(raw, dict) or not raw:
        raise AlarmCatalogError("El catálogo debe tener un objeto 'messages' no vacío")
    if not all(isinstance(text, str) and text.strip() for text in raw.values()):
        raise AlarmCatalogError("Todos los mensajes fijos deben ser textos no vacíos")
    return {str(key): str(text).strip() for key, text in raw.items()}


def _rule_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Obtiene la lista de reglas del catálogo."""
    items = data.get("rules")
    if not isinstance(items, list) or not items:
        raise AlarmCatalogError("El catálogo debe tener una lista 'rules' no vacía")
    return items


def _parse_rule(item: Any, messages: Mapping[str, str]) -> AlarmRule:
    """Convierte una entrada del catálogo en una AlarmRule validada."""
    if not isinstance(item, dict) or any(name not in item for name in RULE_FIELDS):
        raise AlarmCatalogError(f"Regla incompleta (campos requeridos: {', '.join(RULE_FIELDS)})")
    rule_id = str(item["id"])
    if item["message_id"] not in messages:
        raise AlarmCatalogError(f"{rule_id}: message_id '{item['message_id']}' no existe")
    return AlarmRule(
        id=rule_id,
        domain=_parse_enum(Domain, item["domain"], rule_id, "domain"),
        population=str(item["population"]),
        sign=str(item["sign"]),
        severity=_parse_enum(Severity, item["severity"], rule_id, "severity"),
        patterns=_compile_patterns(item["patterns"], rule_id),
        message_id=str(item["message_id"]),
        source=str(item.get("source", "")),
        code=_parse_code(item["code"], rule_id),
        examples=_parse_examples(item.get("examples", []), rule_id),
    )


def _compile_patterns(raw: Any, rule_id: str) -> tuple[re.Pattern[str], ...]:
    """Compila los patrones de una regla."""
    if not isinstance(raw, list) or not raw or not all(isinstance(p, str) for p in raw):
        raise AlarmCatalogError(f"{rule_id}: 'patterns' debe ser una lista de textos no vacía")
    try:
        return tuple(compile_pattern(pattern) for pattern in raw)
    except re.error as error:
        raise AlarmCatalogError(f"{rule_id}: patrón inválido ({error})") from error


def _parse_enum[E: (Domain, Severity)](enum_type: type[E], raw: Any, rule_id: str, name: str) -> E:
    """Convierte un valor del catálogo al enum indicado."""
    try:
        return enum_type(raw)
    except ValueError as error:
        raise AlarmCatalogError(f"{rule_id}: '{name}' inválido: {raw}") from error


def _parse_code(raw: Any, rule_id: str) -> str:
    """Valida el código del signo: MAYÚSCULAS, números y guiones bajos (ADR 0012)."""
    if not isinstance(raw, str) or not CODE_PATTERN.match(raw):
        raise AlarmCatalogError(f"{rule_id}: 'code' debe ser p. ej. VOMITA_TODO, no {raw!r}")
    return raw


def _parse_examples(raw: Any, rule_id: str) -> tuple[str, ...]:
    """Valida los ejemplos coloquiales del signo (lista de textos, puede faltar)."""
    if not isinstance(raw, list) or not all(isinstance(e, str) and e.strip() for e in raw):
        raise AlarmCatalogError(f"{rule_id}: 'examples' debe ser una lista de textos")
    return tuple(example.strip() for example in raw)


def _check_unique(label: str, values: list[str]) -> None:
    """Verifica que no haya valores repetidos (IDs de regla o códigos de signo)."""
    duplicated = sorted({value for value in values if values.count(value) > 1})
    if duplicated:
        raise AlarmCatalogError(f"{label} repetidos: {', '.join(duplicated)}")
