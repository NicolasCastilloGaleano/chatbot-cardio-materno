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
