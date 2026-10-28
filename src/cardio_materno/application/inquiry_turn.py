"""Turno de indagación de la HU-11 (ADR 0017): preguntas verificadas, sin afirmaciones de salud.

El agente redacta 1 o 2 preguntas orientadas por los candidatos del RAG (que no son
evidencia). Una verificación determinista (`domain/grounding.py::verify_inquiry`) conserva
solo preguntas cortas y cortesía; si no queda ninguna pregunta, se usa una pregunta fija.
"""

from collections.abc import Sequence

from cardio_materno.application.grounded_reply import SENTENCE_SEPARATOR, GroundedReply
from cardio_materno.domain.grounding import GroundingPolicy, has_question, verify_inquiry
from cardio_materno.domain.trace import GroundingCheck

# Pregunta fija cuando ninguna pregunta del agente pasa la verificación.
INQUIRY_FALLBACK_QUESTION = "¿Me puedes contar qué sientes, desde cuándo y a quién le pasa?"


def compose_inquiry(
    draft: Sequence[str], user_texts: Sequence[str], policy: GroundingPolicy
) -> GroundedReply:
    """Verifica las preguntas del agente y arma el turno de indagación.

    Args:
        draft: Frases que redactó el agente.
        user_texts: Mensajes de la persona en el hilo (para aceptar los números que dijo).
        policy: Parámetros de la verificación.

    Returns:
        Las frases aceptadas o, si no queda ninguna pregunta, las de cortesía aceptadas y la
        pregunta fija. Nunca cita evidencia; la verificación queda en `check`.
    """
    kept, dropped = verify_inquiry(draft, user_texts, policy)
    check = GroundingCheck(len(kept), len(draft), False, dropped)
    shown = kept if has_question(kept) else (*kept, INQUIRY_FALLBACK_QUESTION)
    return GroundedReply(SENTENCE_SEPARATOR.join(shown), (), check)
