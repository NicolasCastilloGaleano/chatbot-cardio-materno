"""Textos fijos de los canales de chat y división de respuestas largas (HU-09)."""

import re

UNSUPPORTED_MESSAGE_TEXT = (
    "Por ahora solo puedo leer mensajes de texto. Escríbeme tu consulta, por favor."
)
WAIT_NOTICE_TEXT = "Estoy revisando tu mensaje, dame un momento por favor."
# Sin consejo clínico propio: si el mensaje tenía una alarma, el servicio ya respondió con su
# texto fijo aunque el modelo fallara (HU-04). Cualquier texto de urgencia lo decide el equipo.
MODEL_ERROR_TEXT = (
    "No pude preparar una respuesta en este momento. Intenta de nuevo en unos minutos."
)
# Consentimiento (HU-01). Textos PROVISIONALES: su redacción y su alcance jurídico los
# aprueban el equipo y los aliados (docs/00-gestion/pendientes-aprobacion.md, punto 9).
CONSENT_REQUEST_TEXT = (
    "Hola. Soy un asistente de teleorientación en salud del corazón, la presión arterial, "
    "el embarazo y el cuidado del bebé. Doy información educativa: no hago diagnósticos, no "
    "receto medicamentos y no reemplazo al personal de salud.\n\n"
    "Para orientarte necesito guardar los mensajes de esta conversación. No guardo tu "
    "nombre ni tu número de teléfono.\n\n"
    "¿Aceptas? Responde SÍ o NO.\n\n"
    "Si es una emergencia, llama al 123 o acude a urgencias."
)
CONSENT_ACCEPTED_TEXT = "Gracias. Ya puedes contarme tu duda o lo que sientes."
CONSENT_REJECTED_TEXT = (
    "Entendido: no guardaré tu conversación y no podré orientarte por este medio. Si "
    "cambias de opinión, escríbeme de nuevo. Si es una emergencia, llama al 123 o acude a "
    "urgencias."
)
WHATSAPP_MAX_CHARS = 4096
_TOKEN = re.compile(r"\s+|\S+")


def split_message(text: str, limit: int = WHATSAPP_MAX_CHARS) -> list[str]:
    """Divide un texto en partes de máximo `limit` caracteres sin cortar palabras.

    Una palabra más larga que el límite (p. ej., una URL) sí se corta.

    Args:
        text: Texto completo.
        limit: Máximo de caracteres por parte.

    Returns:
        Las partes en orden, sin espacios sobrantes en los bordes.
    """
    parts: list[str] = []
    current = ""
    for token in _TOKEN.findall(text.strip()):
        if len(current) + len(token) <= limit:
            current += token
            continue
        parts.append(current.rstrip())
        current = "" if token.isspace() else token
        while len(current) > limit:
            parts.append(current[:limit])
            current = current[limit:]
    parts.append(current.rstrip())
    return [part for part in parts if part]
