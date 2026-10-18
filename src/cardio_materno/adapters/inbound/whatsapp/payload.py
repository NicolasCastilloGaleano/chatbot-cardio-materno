"""Conversión del payload del webhook de WhatsApp Cloud API a `IncomingMessage` (ADR 0014).

Estructura relevante del payload:
    {"entry": [{"changes": [{"field": "messages", "value": {
        "messages": [{"from": "<wa_id>", "id": "wamid…", "type": "text",
                      "text": {"body": "…"}}],
        "statuses": [...]}}]}]}

El nombre de perfil (`contacts[].profile.name`) se descarta y el `wa_id` solo se usa como
dirección de respuesta (en memoria) y para calcular el hash de la identidad.
"""

from collections.abc import Iterator
from typing import Any

from cardio_materno.application.incoming_message import (
    IdentityHasher,
    IncomingMessage,
    MessageKind,
)
from cardio_materno.domain.user import Channel

MESSAGES_FIELD = "messages"
TEXT_TYPE = "text"
# Reacciones con emoji y avisos del sistema no son consultas: no se responden.
SILENT_TYPES = frozenset({"reaction", "system"})


def parse_messages(payload: dict[str, Any], hasher: IdentityHasher) -> list[IncomingMessage]:
    """Extrae los mensajes de un payload del webhook.

    Las notificaciones de estado (enviado, entregado, leído) no generan mensajes.

    Args:
        payload: Cuerpo JSON de la notificación.
        hasher: Función que seudonimiza el `wa_id`.

    Returns:
        Mensajes normalizados, en el orden del payload.
    """
    return [
        to_incoming(raw, hasher)
        for raw in _raw_messages(payload)
        if raw.get("type") not in SILENT_TYPES and raw.get("from") and raw.get("id")
    ]


def to_incoming(raw: dict[str, Any], hasher: IdentityHasher) -> IncomingMessage:
    """Normaliza un mensaje del payload.

    Args:
        raw: Un elemento de `value.messages`.
        hasher: Función que seudonimiza el `wa_id`.

    Returns:
        El mensaje normalizado (texto o no soportado).
    """
    channel_kind = str(raw.get("type", ""))
    text = _text_body(raw) if channel_kind == TEXT_TYPE else ""
    kind = MessageKind.TEXT if text else MessageKind.UNSUPPORTED
    sender = str(raw["from"])
    return IncomingMessage(
        Channel.WHATSAPP, str(raw["id"]), hasher(sender), sender, kind, channel_kind, text
    )


def _raw_messages(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Recorre `entry[].changes[].value.messages[]` tolerando campos ausentes."""
    for entry in _dicts(payload.get("entry")):
        for change in _dicts(entry.get("changes")):
            if change.get("field") != MESSAGES_FIELD:
                continue
            value = change.get("value")
            if isinstance(value, dict):
                yield from _dicts(value.get("messages"))


def _dicts(items: object) -> Iterator[dict[str, Any]]:
    """Elementos de una lista que son objetos JSON (ignora lo demás)."""
    if isinstance(items, list):
        yield from (item for item in items if isinstance(item, dict))


def _text_body(raw: dict[str, Any]) -> str:
    """Texto de un mensaje de tipo texto, sin espacios en los bordes."""
    text = raw.get("text")
    body = text.get("body", "") if isinstance(text, dict) else ""
    return str(body).strip()
