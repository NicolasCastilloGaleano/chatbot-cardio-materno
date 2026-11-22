"""Escalamiento al profesional de salud de los turnos sin evidencia (HU-16, ADR 0022).

Un turno escala cuando es un vacío de la HU-15 (`gaps.gap_of`: la abstención por falta de
información o el cierre honesto) y no hubo alarma: las alarmas salen siempre de inmediato y
nunca esperan a una persona. Con `ESCALATION_MODE=activo`, la abstención se reemplaza por un
aviso de espera; con `observar`, la persona ve la abstención de siempre y el caso solo se
registra.
"""

from enum import StrEnum

from cardio_materno.application.agent_turn import AnalysisTurn
from cardio_materno.application.gaps import Gap, gap_of
from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    CLOSING_TEXT,
    NO_INFORMATION_TEXT,
)
from cardio_materno.domain.escalation import CaseSnapshot
from cardio_materno.domain.trace import ReplyTrace

# Plantillas pendientes de revisión clínica (ADR 0022).
WAITING_TEXT = (
    "Tu consulta fue enviada a un profesional de salud, que te responderá en este mismo chat. "
    "Si los síntomas empeoran o aparece algo nuevo que te preocupe, acude de inmediato a un "
    "servicio de salud o llama a la línea de emergencias 123."
)
ALREADY_WAITING_TEXT = (
    "Tu consulta sigue en revisión por un profesional de salud, que te responderá en este "
    "mismo chat. Si los síntomas empeoran, acude de inmediato a un servicio de salud o llama a "
    "la línea de emergencias 123."
)
# Orden de reemplazo: la abstención que pide detalles contiene a la que no los pide.
REPLACEABLE_TEXTS = (ABSTENTION_TEXT, NO_INFORMATION_TEXT, CLOSING_TEXT)


class EscalationMode(StrEnum):
    """Cómo participa el escalamiento (`ESCALATION_MODE`)."""

    OFF = "apagado"
    OBSERVE = "observar"
    ACTIVE = "activo"


def escalation_gap(reply: str, trace: ReplyTrace | None, alarmed: bool) -> Gap | None:
    """El vacío que escala, o None si el turno no debe llegar al profesional.

    Args:
        reply: Respuesta que vería la persona.
        trace: Traza de la respuesta.
        alarmed: True si el turno tuvo una alarma (nunca escala).

    Returns:
        El vacío de la HU-15, o None.
    """
    return None if alarmed else gap_of(reply, trace)


def with_waiting_text(reply: str, waiting: str) -> str:
    """Reemplaza la abstención o el cierre por el aviso de espera.

    Conserva lo que vaya antes, como el recordatorio de una alarma ya avisada (ADR 0018).
    """
    for text in REPLACEABLE_TEXTS:
        if text in reply:
            return reply.replace(text, waiting)
    return reply


def snapshot_of(gap: Gap, analysis: AnalysisTurn) -> CaseSnapshot:
    """Resumen clínico del caso con lo que ya guardan el análisis y la traza.

    No incluye el mensaje de la persona ni datos de identificación.
    """
    return CaseSnapshot(
        domain=analysis.domain,
        summary=analysis.summary,
        symptoms=analysis.reported_symptoms,
        signs=analysis.reported_signs,
        query=gap.query,
        reason=str(gap.reason),
        category=gap.category,
        best_score=gap.best_score,
    )
