"""Contratos de las dos llamadas al agente (HU-06, HU-02; ADR 0006, 0008).

- **Análisis** (sin evidencia): hilo, dominio, resumen y síntomas reportados → filtro 2.
- **Respuesta** (con evidencia): texto para el usuario y etiquetas de evidencia citadas.

Se separan para que la evidencia del RAG nunca influya en los síntomas que revisan las
reglas de alarma.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import Domain


class ThreadAction(StrEnum):
    """Decisión del agente sobre el hilo actual."""

    CONTINUE = "continuar"
    NEW = "nuevo"


class Scope(StrEnum):
    """Alcance del mensaje según su propósito completo (HU-07, ADR 0009)."""

    IN_SCOPE = "en_alcance"
    CONVERSATIONAL = "conversacional"
    OUT_OF_SCOPE = "fuera_de_alcance"


# JSON Schema de la llamada de análisis.
ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thread_action": {"type": "string", "enum": [a.value for a in ThreadAction]},
        "domain": {"type": "string", "enum": [d.value for d in Domain]},
        "summary": {"type": "string"},
        "reported_symptoms": {"type": "array", "items": {"type": "string"}},
        "scope": {"type": "string", "enum": [s.value for s in Scope]},
        "scope_reason": {"type": "string"},
    },
    "required": [
        "thread_action",
        "domain",
        "summary",
        "reported_symptoms",
        "scope",
        "scope_reason",
    ],
}

MSG_INVALID_TURN = "El modelo no devolvió la estructura esperada ({detail})."


@dataclass(frozen=True)
class AnalysisTurn:
    """Resultado validado de la llamada de análisis.

    Attributes:
        thread_action: Si el mensaje continúa el hilo o empieza un tema nuevo.
        domain: Dominio de salud del hilo resultante.
        summary: Resumen del hilo hasta el mensaje actual del usuario.
        reported_symptoms: Síntomas que la persona dice tener o haber tenido (filtro 2, ADR 0007).
        scope: Alcance del mensaje completo (HU-07, ADR 0009).
        scope_reason: Motivo corto de la decisión de alcance (para auditar).
    """

    thread_action: ThreadAction
    domain: Domain
    summary: str
    reported_symptoms: tuple[str, ...] = ()
    scope: Scope = Scope.IN_SCOPE
    scope_reason: str = ""


@dataclass(frozen=True)
class ReplyTurn:
    """Resultado validado de la llamada de respuesta.

    Attributes:
        reply: Texto que se muestra al usuario.
        evidence_ids: Etiquetas de evidencia que el agente dice usar (E1, E2…).
    """

    reply: str
    evidence_ids: tuple[str, ...] = ()


def parse_analysis(data: dict[str, Any]) -> AnalysisTurn:
    """Valida el JSON de la llamada de análisis.

    Raises:
        LanguageModelError: Si falta un campo, está vacío o tiene un valor no permitido.
    """
    return AnalysisTurn(
        thread_action=_parse_enum(ThreadAction, data, "thread_action"),
        domain=_parse_enum(Domain, data, "domain"),
        summary=_required_text(data, "summary"),
        reported_symptoms=_text_list(data, "reported_symptoms"),
        scope=_parse_enum(Scope, data, "scope"),
        scope_reason=_optional_text(data, "scope_reason"),
    )


def reply_schema(labels: Sequence[str]) -> dict[str, Any]:
    """JSON Schema de la llamada de respuesta; las citas se limitan a las etiquetas ofrecidas."""
    items: dict[str, Any] = (
        {"type": "string", "enum": list(labels)} if labels else {"type": "string"}
    )
    citations: dict[str, Any] = {"type": "array", "items": items}
    if not labels:
        citations["maxItems"] = 0
    return {
        "type": "object",
        "properties": {"reply": {"type": "string"}, "evidence_ids": citations},
        "required": ["reply", "evidence_ids"],
    }


def parse_reply(data: dict[str, Any], labels: Sequence[str]) -> ReplyTurn:
    """Valida el JSON de la llamada de respuesta.

    Raises:
        LanguageModelError: Si falta el texto o se cita una etiqueta que no se ofreció.
    """
    cited = _text_list(data, "evidence_ids")
    unknown = sorted(set(cited) - set(labels))
    if unknown:
        detail = f"cita evidencia no ofrecida: {', '.join(unknown)}"
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=detail))
    return ReplyTurn(reply=_required_text(data, "reply"), evidence_ids=tuple(dict.fromkeys(cited)))


def _required_text(data: dict[str, Any], field: str) -> str:
    """Obtiene un texto obligatorio y no vacío."""
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=f"'{field}' vacío o ausente"))
    return value.strip()


def _optional_text(data: dict[str, Any], field: str) -> str:
    """Obtiene un texto opcional (vacío si falta)."""
    value = data.get(field, "")
    if not isinstance(value, str):
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=f"'{field}' debe ser texto"))
    return value.strip()


def _text_list(data: dict[str, Any], field: str) -> tuple[str, ...]:
    """Obtiene una lista obligatoria de textos; descarta los vacíos."""
    value = data.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        detail = f"'{field}' debe ser una lista de textos"
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=detail))
    return tuple(item.strip() for item in value if item.strip())


def _parse_enum[E: StrEnum](enum_type: type[E], data: dict[str, Any], field: str) -> E:
    """Convierte un campo en un valor del enum indicado."""
    raw = _required_text(data, field)
    try:
        return enum_type(raw)
    except ValueError as error:
        detail = f"'{field}' con valor no permitido: {raw}"
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=detail)) from error
