"""Seguimiento del estado del caso con la base v2 (MIG-09, ADR 0018).

El estado del caso no tiene almacenamiento propio: viaja en la traza de cada respuesta del
asistente (`case_motive`, `case_stage`, `case_visited`) y se recupera de los mensajes
recientes del hilo. Así no cambian los esquemas de JSON ni de SQLite.

En este paso el estado solo se **observa**: se toma del registro principal que citó la
respuesta, sin cambiar cómo se busca la evidencia (eso es MIG-10 y MIG-11).
"""

from collections.abc import Sequence

from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.domain.case_state import CaseState, advance
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import EvidenceItem, Stage


def case_after_reply(
    analysis: AnalysisTurn,
    recent: Sequence[ChatMessage],
    items: Sequence[EvidenceItem],
    cited: Sequence[str],
) -> CaseState | None:
    """Estado del caso después de una respuesta con evidencia.

    Args:
        analysis: Análisis del turno (si marca un tema nuevo, el caso empieza de nuevo).
        recent: Mensajes recientes del hilo, con las trazas del asistente.
        items: Evidencia ofrecida al agente.
        cited: Etiquetas de los registros que respaldan la respuesta, el principal primero.

    Returns:
        El estado con el cuadro y la etapa del registro principal, o None si ese registro
        no es de la base v2.
    """
    entry = next((item.entry for item in items if cited and item.label == cited[0]), None)
    if entry is None or not entry.motive or entry.stage is None:
        return None
    previous = case_from_recent(recent) if analysis.thread_action is ThreadAction.CONTINUE else None
    return advance(previous, entry.motive, entry.stage)


def case_from_recent(recent: Sequence[ChatMessage]) -> CaseState | None:
    """Estado del caso guardado en la traza de la última respuesta del asistente que lo tenga.

    Returns:
        El estado, o None si ninguna respuesta reciente tiene cuadro (o la traza es inválida).
    """
    for message in reversed(recent):
        trace = message.trace
        if message.role is Role.ASSISTANT and trace is not None and trace.case_motive:
            return parse_case(trace.case_motive, trace.case_stage, trace.case_visited)
    return None


def parse_case(motive: str, stage: str, visited: Sequence[str]) -> CaseState | None:
    """Reconstruye el estado desde la traza (None si una etapa no es válida)."""
    try:
        return CaseState(motive, Stage(stage), tuple(Stage(item) for item in visited))
    except ValueError:
        return None
