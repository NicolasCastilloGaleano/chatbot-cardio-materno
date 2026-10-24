"""Control de alcance del mensaje (HU-07, ADR 0009).

El alcance lo decide la llamada de análisis según el **propósito del mensaje completo**
(las menciones a otros temas que solo dan contexto no lo sacan del alcance). Aquí se aplican
las reglas deterministas de seguridad sobre esa decisión.
"""

from collections.abc import Sequence

from cardio_materno.application.agent_turn import AnalysisTurn, Scope, ThreadAction
from cardio_materno.domain.conversation import ChatMessage, Role

OUT_OF_SCOPE_MESSAGE = (
    "Este servicio solo orienta sobre salud del corazón y la presión arterial, el embarazo, "
    "el parto, el posparto, la lactancia y los niños pequeños. Sobre ese tema no puedo ayudarte. "
    "¿Tienes alguna duda o molestia sobre estos temas que quieras contarme?"
)
CONVERSATIONAL_CONTEXT = (
    "MENSAJE CONVERSACIONAL (saludo, agradecimiento o despedida): responde con amabilidad y "
    "presenta brevemente el servicio. No hagas afirmaciones de salud. No hay evidencia."
)
QUESTION_MARK = "?"


def effective_scope(analysis: AnalysisTurn, recent: Sequence[ChatMessage] = ()) -> Scope:
    """Alcance que se aplica: quien reporta un síntoma o responde una pregunta no se descarta.

    Desde el 2026-10-17 (prompt de análisis v6, decisión de Nicolas Castillo Galeano), un
    síntoma reportado basta aunque su dominio sea incierto ("ninguno"): un dolor de brazo
    atribuido a un susto puede ser cardíaco, y se indaga en lugar de descartarlo.

    Desde el plan de migración (MIG-01), un mensaje que continúa el hilo cuando el asistente
    dejó una pregunta pendiente ("sí, desde ayer", "no sé") tampoco se descarta: es la
    respuesta a esa pregunta, aunque no traiga síntomas. Cuenta cualquier pregunta del último
    mensaje del asistente, no solo la final: los registros de la base v1 suelen preguntar en
    medio del texto ("¿Hubo caída…? … solicita valoración.").

    Args:
        analysis: Resultado de la llamada de análisis.
        recent: Mensajes recientes del hilo activo (vacío si no hay hilo).

    Returns:
        `en_alcance` si hay signos del catálogo marcados, síntomas reportados o una respuesta
        a una pregunta pendiente; si no, el alcance que decidió el análisis.
    """
    if analysis.reported_signs or analysis.reported_symptoms:
        return Scope.IN_SCOPE
    if analysis.scope is Scope.OUT_OF_SCOPE and answers_pending_question(analysis, recent):
        return Scope.IN_SCOPE
    return analysis.scope


def answers_pending_question(analysis: AnalysisTurn, recent: Sequence[ChatMessage]) -> bool:
    """True si el mensaje continúa el hilo y el último mensaje del asistente pregunta algo.

    Un mensaje que el análisis marca como tema nuevo ("¿quién ganó el partido?") no cuenta
    como respuesta, aunque haya una pregunta pendiente.
    """
    if analysis.thread_action is not ThreadAction.CONTINUE:
        return False
    return has_pending_question(recent)


def has_pending_question(recent: Sequence[ChatMessage]) -> bool:
    """True si el último mensaje del asistente en el hilo contiene una pregunta."""
    replies = [message for message in recent if message.role is Role.ASSISTANT]
    return bool(replies) and QUESTION_MARK in replies[-1].content
