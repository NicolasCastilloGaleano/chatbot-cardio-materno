"""Contrato de la respuesta estructurada del agente (HU-06, ADR 0006)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import Domain


class ThreadAction(StrEnum):
    """Decisión del agente sobre el hilo actual."""

    CONTINUE = "continuar"
    NEW = "nuevo"


# JSON Schema que se envía al modelo para restringir su salida.
AGENT_TURN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thread_action": {"type": "string", "enum": [a.value for a in ThreadAction]},
        "domain": {"type": "string", "enum": [d.value for d in Domain]},
        "summary": {"type": "string"},
        "reply": {"type": "string"},
    },
    "required": ["thread_action", "domain", "summary", "reply"],
}

MSG_INVALID_TURN = "El modelo no devolvió la estructura esperada ({detail})."


@dataclass(frozen=True)
class AgentTurn:
    """Respuesta del agente ya validada.

    Attributes:
        thread_action: Si el mensaje continúa el hilo o empieza un tema nuevo.
        domain: Dominio de salud del hilo resultante.
        summary: Resumen actualizado del hilo resultante.
        reply: Texto que se muestra al usuario.
    """

    thread_action: ThreadAction
    domain: Domain
    summary: str
    reply: str


def parse_agent_turn(data: dict[str, Any]) -> AgentTurn:
    """Valida el JSON del modelo y lo convierte en un AgentTurn.

    Args:
        data: Objeto JSON devuelto por el modelo.

    Returns:
        La respuesta validada.

    Raises:
        LanguageModelError: Si falta un campo, está vacío o tiene un valor no permitido.
    """
    return AgentTurn(
        thread_action=_parse_enum(ThreadAction, data, "thread_action"),
        domain=_parse_enum(Domain, data, "domain"),
        summary=_required_text(data, "summary"),
        reply=_required_text(data, "reply"),
    )


def _required_text(data: dict[str, Any], field: str) -> str:
    """Obtiene un texto obligatorio y no vacío."""
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=f"'{field}' vacío o ausente"))
    return value.strip()


def _parse_enum[E: StrEnum](enum_type: type[E], data: dict[str, Any], field: str) -> E:
    """Convierte un campo en un valor del enum indicado."""
    raw = _required_text(data, field)
    try:
        return enum_type(raw)
    except ValueError as error:
        detail = f"'{field}' con valor no permitido: {raw}"
        raise LanguageModelError(MSG_INVALID_TURN.format(detail=detail)) from error
