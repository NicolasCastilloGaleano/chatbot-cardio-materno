"""Auditor determinista de la salida: la respuesta deja la conversación abierta (MIG-12).

Si la respuesta con evidencia no termina en una pregunta, se le agrega la pregunta final del
registro que la respalda, tal como está escrita en él. Como sale del registro, no agrega
ninguna afirmación sin respaldo y no requiere volver a llamar al LLM.
"""

from collections.abc import Sequence

from cardio_materno.domain.knowledge import KnowledgeEntry

QUESTION_OPEN = "¿"
QUESTION_CLOSE = "?"
SENTENCE_SEPARATOR = " "


def closing_question(answer: str) -> str | None:
    """Pregunta con la que termina un texto ("¿…?"), o None si no termina en pregunta."""
    text = answer.rstrip()
    start = text.rfind(QUESTION_OPEN)
    if not text.endswith(QUESTION_CLOSE) or start < 0:
        return None
    return text[start:]


def ensure_closing_question(reply: str, entries: Sequence[KnowledgeEntry]) -> str:
    """Agrega la pregunta final del primer registro que la tenga si la respuesta no pregunta.

    Args:
        reply: Respuesta ya verificada.
        entries: Registros que respaldan la respuesta, el principal primero.

    Returns:
        La respuesta sin cambios si ya termina en pregunta (o ningún registro tiene una);
        si no, la respuesta seguida de esa pregunta.
    """
    if reply.rstrip().endswith(QUESTION_CLOSE):
        return reply
    for entry in entries:
        question = closing_question(entry.answer)
        if question is not None and question not in reply:
            return f"{reply.rstrip()}{SENTENCE_SEPARATOR}{question}"
    return reply
