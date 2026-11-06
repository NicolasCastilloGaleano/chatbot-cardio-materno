"""Turno de indagación de la HU-11 (ADR 0017): preguntas verificadas, sin afirmaciones de salud.

El agente redacta 1 o 2 preguntas orientadas por los candidatos del RAG (que no son
evidencia). Una verificación determinista (`domain/grounding.py::verify_inquiry`) conserva
solo preguntas cortas y cortesía; si no queda ninguna pregunta, se usa una pregunta fija.
"""

from collections.abc import Sequence
from dataclasses import replace

from cardio_materno.application.grounded_reply import SENTENCE_SEPARATOR, GroundedReply
from cardio_materno.domain.grounding import (
    GroundingPolicy,
    has_question,
    repeats_question,
    verify_inquiry,
)
from cardio_materno.domain.trace import GroundingCheck

# Pregunta fija cuando ninguna pregunta del agente pasa la verificación.
INQUIRY_FALLBACK_QUESTION = "¿Me puedes contar qué sientes, desde cuándo y a quién le pasa?"


def verified_question(
    draft: Sequence[str],
    user_texts: Sequence[str],
    policy: GroundingPolicy,
    asked: Sequence[str] = (),
) -> str:
    """Pregunta que acompaña una respuesta (HU-13); vacía si ninguna pasa la verificación.

    Args:
        draft: Frases que redactó el agente.
        user_texts: Mensajes de la persona en el hilo (para aceptar los números que dijo).
        policy: Parámetros de la verificación.
        asked: Preguntas de la última respuesta del hilo, que no se repiten.

    Returns:
        Las preguntas aceptadas, hasta el máximo. Nunca usa la pregunta fija: la persona ya
        recibió una respuesta.
    """
    limit = replace(policy, max_inquiry_sentences=policy.max_questions_with_answer)
    questions = [s for s in draft if has_question([s]) and not repeats_question(s, asked, policy)]
    kept, _ = verify_inquiry(questions, user_texts, limit)
    return SENTENCE_SEPARATOR.join(kept)


def compose_inquiry(
    draft: Sequence[str],
    user_texts: Sequence[str],
    policy: GroundingPolicy,
    asked: Sequence[str] = (),
) -> GroundedReply:
    """Verifica las preguntas del agente y arma el turno de indagación.

    Args:
        draft: Frases que redactó el agente.
        user_texts: Mensajes de la persona en el hilo (para aceptar los números que dijo).
        policy: Parámetros de la verificación.
        asked: Preguntas de la última respuesta del hilo: una pregunta que las repite se
            descarta, salvo que todas las repitan.

    Returns:
        Las frases aceptadas. Si todas las preguntas repiten las anteriores, solo la primera
        de ellas: la persona no la respondió, y la pregunta fija le pediría lo que ya contó
        (guion del 2026-11-06). Si aun así no queda ninguna pregunta, la pregunta fija. Nunca
        cita evidencia; la verificación queda en `check`.
    """
    repeated = tuple(s for s in draft if repeats_question(s, asked, policy))
    fresh = [s for s in draft if s not in repeated]
    kept, dropped = verify_inquiry(fresh, user_texts, policy)
    if not has_question(kept) and repeated:
        again, _ = verify_inquiry(repeated[:1], user_texts, policy)
        kept = (*kept, *again)
    left_out = tuple(s for s in (*repeated, *dropped) if s not in kept)
    check = GroundingCheck(len(kept), len(draft), False, left_out)
    shown = kept if has_question(kept) else (*kept, INQUIRY_FALLBACK_QUESTION)
    return GroundedReply(SENTENCE_SEPARATOR.join(shown), (), check)
