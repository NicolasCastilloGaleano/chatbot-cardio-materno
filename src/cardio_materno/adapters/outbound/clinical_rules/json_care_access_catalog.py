"""Carga y valida `knowledge/care_access.json` y `knowledge/public_info.json` (ADR 0023).

Son contenido versionado como datos: el equipo los revisa y aprueba sin leer código. Un
archivo con errores impide arrancar (falla rápido) para no operar con textos incompletos.
"""

import json
import re
from pathlib import Path
from typing import Any

from cardio_materno.domain.alarms import compile_pattern
from cardio_materno.domain.care_access import (
    CareAccessCatalog,
    CareFact,
    CascadeQuestion,
    CascadeStep,
    FactGroup,
    Notice,
    NoticeKind,
    NoticeRoute,
    PublicEmergencyInfo,
)

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
STATUSES = frozenset({"pendiente", "aprobado"})


class CareAccessCatalogError(ValueError):
    """El catálogo de acceso o la información pública no existen o tienen un error."""


def load_care_access_catalog(path: Path) -> CareAccessCatalog:
    """Lee y valida el catálogo de acceso.

    Raises:
        CareAccessCatalogError: Si el archivo no existe, no es JSON o su contenido es inválido.
    """
    data = _read_json(path)
    try:
        facts = tuple(_parse_fact(item) for item in data["facts"])
        notices = {code: _parse_notice(code, item) for code, item in data["notices"].items()}
        questions = {
            CascadeStep(step): _parse_question(CascadeStep(step), item)
            for step, item in data["cascade_questions"].items()
        }
        catalog = CareAccessCatalog(
            version=str(data["version"]),
            facts=facts,
            notices=notices,
            questions=questions,
            topic_patterns=tuple(compile_pattern(p) for p in data.get("topic_patterns", [])),
            research_text=str(data.get("research_authorization", {}).get("text", "")),
        )
    except (KeyError, TypeError, ValueError, AttributeError, re.error) as error:
        raise CareAccessCatalogError(f"Catálogo de acceso inválido ({path}): {error}") from error
    _check(catalog, path)
    return catalog


def load_public_emergency_info(path: Path) -> PublicEmergencyInfo:
    """Lee la información pública de emergencias.

    Raises:
        CareAccessCatalogError: Si el archivo no existe, no es JSON o le faltan campos.
    """
    data = _read_json(path)
    try:
        emergency = data["emergency"]
        return PublicEmergencyInfo(
            version=str(data["version"]),
            status=str(data["validation_status"]),
            title=str(emergency["title"]),
            phone=str(emergency["phone"]),
            lines=tuple(str(line) for line in emergency["lines"]),
            disclaimer=str(emergency["disclaimer"]),
        )
    except (KeyError, TypeError) as error:
        raise CareAccessCatalogError(f"Información pública inválida ({path}): {error}") from error


def _read_json(path: Path) -> dict[str, Any]:
    """Lee el archivo y verifica que sea un objeto JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CareAccessCatalogError(f"No existe el archivo: {path}") from error
    except json.JSONDecodeError as error:
        raise CareAccessCatalogError(f"El archivo no es JSON válido ({path}): {error}") from error
    if not isinstance(data, dict):
        raise CareAccessCatalogError(f"El archivo debe ser un objeto JSON: {path}")
    return data


def _parse_fact(item: dict[str, Any]) -> CareFact:
    """Convierte un dato del catálogo."""
    code = str(item["code"])
    if not CODE_PATTERN.match(code):
        raise ValueError(f"código inválido: {code!r}")
    group = FactGroup(item["group"])
    step = CascadeStep(item["step"]) if "step" in item else None
    if (group is FactGroup.CASCADE) != (step is not None and isinstance(item.get("value"), bool)):
        raise ValueError(f"{code}: solo los datos de la cascada llevan 'step' y 'value'")
    return CareFact(
        code=code,
        group=group,
        label=str(item["label"]),
        examples=tuple(str(example) for example in item.get("examples", [])),
        patterns=tuple(compile_pattern(pattern) for pattern in item.get("patterns", [])),
        step=step,
        value=item.get("value"),
        barrier=str(item.get("barrier", "")),
    )


def _parse_notice(code: str, item: dict[str, Any]) -> Notice:
    """Convierte un aviso con su procedencia y su estado."""
    texts = {NoticeRoute(route): str(text) for route, text in item["texts"].items()}
    if not texts or any(not text.strip() for text in texts.values()):
        raise ValueError(f"{code}: el aviso necesita al menos un texto no vacío")
    return Notice(
        code=code,
        kind=NoticeKind(item["kind"]),
        status=_status(code, item),
        texts=texts,
        basis=tuple(str(entry) for entry in item.get("basis", [])),
        source_ids=tuple(str(entry) for entry in item.get("source_ids", [])),
    )


def _parse_question(step: CascadeStep, item: dict[str, Any]) -> CascadeQuestion:
    """Convierte una pregunta de la cascada."""
    text = str(item["text"]).strip()
    if not text.endswith("?"):
        raise ValueError(f"la pregunta de '{step}' debe terminar en '?'")
    return CascadeQuestion(step, text, _status(str(step), item))


def _status(name: str, item: dict[str, Any]) -> str:
    """Estado de aprobación de un texto."""
    status = str(item["status"])
    if status not in STATUSES:
        raise ValueError(f"{name}: estado desconocido {status!r}")
    return status


def _check(catalog: CareAccessCatalog, path: Path) -> None:
    """Verifica códigos únicos y que cada aviso corresponda a una barrera o a una brecha."""
    codes = catalog.codes
    if len(set(codes)) != len(codes):
        raise CareAccessCatalogError(f"Códigos repetidos en el catálogo de acceso ({path})")
    barriers = {fact.code for fact in catalog.facts if fact.group is FactGroup.BARRIER}
    stray = [code for code in catalog.notices if code not in barriers and code in codes]
    if stray:
        raise CareAccessCatalogError(f"Avisos sobre datos que no son barreras ({path}): {stray}")
