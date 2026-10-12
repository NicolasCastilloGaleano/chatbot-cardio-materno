"""Control de alcance del mensaje (HU-07, ADR 0009).

El alcance lo decide la llamada de análisis según el **propósito del mensaje completo**
(las menciones a otros temas que solo dan contexto no lo sacan del alcance). Aquí se aplican
las reglas deterministas de seguridad sobre esa decisión.
"""

from cardio_materno.application.agent_turn import AnalysisTurn, Scope
from cardio_materno.domain.conversation import Domain

OUT_OF_SCOPE_MESSAGE = (
    "Este servicio solo orienta sobre salud del corazón y la presión arterial, el embarazo, "
    "el parto, el posparto, la lactancia y los niños pequeños. Sobre ese tema no puedo ayudarte. "
    "Si tienes una duda sobre estos temas, cuéntame."
)
CONVERSATIONAL_CONTEXT = (
    "MENSAJE CONVERSACIONAL (saludo, agradecimiento o despedida): responde con amabilidad y "
    "presenta brevemente el servicio. No hagas afirmaciones de salud. No hay evidencia."
)


def effective_scope(analysis: AnalysisTurn) -> Scope:
    """Alcance que se aplica: quien reporta síntomas de nuestros dominios nunca se descarta.

    Args:
        analysis: Resultado de la llamada de análisis.

    Returns:
        `en_alcance` si hay signos del catálogo marcados, o síntomas reportados con un dominio
        distinto de "ninguno"; si no, el alcance que decidió el análisis.
    """
    if analysis.reported_signs:
        return Scope.IN_SCOPE
    if analysis.reported_symptoms and analysis.domain is not Domain.NONE:
        return Scope.IN_SCOPE
    return analysis.scope
