"""Armado del contexto que recibe cada llamada al agente (HU-06, HU-02)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from cardio_materno.application.agent_turn import AnalysisTurn
from cardio_materno.domain.conversation import ChatMessage, ConversationThread, Role

THREAD_CONTEXT_TEMPLATE = "HILO ACTUAL (JSON):\n{thread_json}"
NO_THREAD_CONTEXT = "HILO ACTUAL: no hay un hilo activo. Este mensaje inicia un hilo nuevo."
CASE_CONTEXT_TEMPLATE = "CASO (análisis de este turno, JSON):\n{case_json}"


@dataclass(frozen=True)
class TurnInput:
    """Mensaje del usuario y mensajes recientes del hilo.

    Attributes:
        user_text: Mensaje actual del usuario.
        recent: Últimos N mensajes del hilo activo (vacío si no hay hilo).
        urgent_reminder: True si en el turno se recuerda una urgencia inmediata ya avisada
            (B-030, ADR 0018): no se indaga y la respuesta acompaña la urgencia.
    """

    user_text: str
    recent: tuple[ChatMessage, ...] = ()
    urgent_reminder: bool = False


def describe_thread(thread: ConversationThread | None) -> str:
    """Describe el hilo actual para el agente, en JSON (o indica que no hay hilo)."""
    if thread is None:
        return NO_THREAD_CONTEXT
    snapshot = {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
    }
    return THREAD_CONTEXT_TEMPLATE.format(thread_json=json.dumps(snapshot, ensure_ascii=False))


def describe_case(analysis: AnalysisTurn) -> str:
    """Describe el resultado del análisis para la llamada de respuesta."""
    case = {
        "domain": str(analysis.domain),
        "summary": analysis.summary,
        "reported_symptoms": list(analysis.reported_symptoms),
    }
    return CASE_CONTEXT_TEMPLATE.format(case_json=json.dumps(case, ensure_ascii=False))


def analysis_context(
    prompt: str, thread: ConversationThread | None, turn: TurnInput
) -> list[ChatMessage]:
    """Contexto de la llamada de análisis. **Nunca incluye evidencia** (ADR 0008)."""
    return _with_history(
        [ChatMessage(Role.SYSTEM, prompt), ChatMessage(Role.SYSTEM, describe_thread(thread))],
        turn,
        extra_system=(),
    )


def reply_context(
    prompt: str, analysis: AnalysisTurn, turn: TurnInput, evidence_text: str
) -> list[ChatMessage]:
    """Contexto de la llamada de respuesta: caso analizado + historial + evidencia."""
    return _with_history(
        [ChatMessage(Role.SYSTEM, prompt), ChatMessage(Role.SYSTEM, describe_case(analysis))],
        turn,
        extra_system=(evidence_text,),
    )


def _with_history(
    head: list[ChatMessage], turn: TurnInput, extra_system: Sequence[str]
) -> list[ChatMessage]:
    """Encabezado + mensajes recientes + mensajes de sistema extra + mensaje del usuario."""
    extras = [ChatMessage(Role.SYSTEM, text) for text in extra_system]
    return [*head, *turn.recent, *extras, ChatMessage(Role.USER, turn.user_text)]
