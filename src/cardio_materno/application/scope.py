"""Control de alcance del mensaje (HU-07, ADR 0009).

El alcance lo decide la llamada de análisis según el **propósito del mensaje completo**
(las menciones a otros temas que solo dan contexto no lo sacan del alcance). Aquí se aplican
las reglas deterministas de seguridad sobre esa decisión.
"""

from cardio_materno.application.agent_turn import AnalysisTurn, Scope

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
    """Alcance que se aplica: quien reporta un síntoma nunca se descarta.

    Desde el 2026-10-17 (prompt de análisis v6, decisión de Nicolas Castillo Galeano), un
    síntoma reportado basta aunque su dominio sea incierto ("ninguno"): un dolor de brazo
    atribuido a un susto puede ser cardíaco, y se indaga en lugar de descartarlo.

    Args:
        analysis: Resultado de la llamada de análisis.

    Returns:
        `en_alcance` si hay signos del catálogo marcados o síntomas reportados; si no, el
        alcance que decidió el análisis.
    """
    if analysis.reported_signs or analysis.reported_symptoms:
        return Scope.IN_SCOPE
    return analysis.scope
