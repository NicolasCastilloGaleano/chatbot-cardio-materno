"""Mensaje entrante común a todos los canales (ADR 0003 y 0014).

Cada adaptador de canal convierte su formato a `IncomingMessage`. La dirección para
responder (`reply_to`) es opaca para la aplicación y **nunca se persiste**: de la identidad
solo se guarda su hash (ADR 0015).
"""

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.domain.user import Channel

IdentityHasher = Callable[[str], str]


class MessageKind(StrEnum):
    """Lo que el asistente puede hacer con el mensaje."""

    TEXT = "texto"
    UNSUPPORTED = "no_soportado"


@dataclass(frozen=True)
class IncomingMessage:
    """Mensaje recibido por un canal, ya normalizado.

    Attributes:
        channel: Canal de origen.
        channel_message_id: Identificador que asigna el canal (para deduplicar).
        user_hash: Hash de la identidad del remitente en el canal.
        reply_to: Dirección del canal para responder (solo en memoria).
        kind: Texto o tipo no soportado.
        channel_kind: Tipo original del canal ("text", "image", "audio"…), para auditoría.
        text: Texto del mensaje ("" si no es de texto).
    """

    channel: Channel
    channel_message_id: str
    user_hash: str
    reply_to: str
    kind: MessageKind
    channel_kind: str
    text: str = ""


def make_identity_hasher(secret: str) -> IdentityHasher:
    """Crea la función que seudonimiza identidades de canal con HMAC-SHA256.

    Args:
        secret: `USER_ID_HASH_SECRET`; sin él no se puede reconstruir el vínculo.

    Returns:
        Función que convierte una identidad (p. ej., el `wa_id`) en su hash hexadecimal.
    """
    key = secret.encode("utf-8")

    def hash_identity(identity: str) -> str:
        return hmac.new(key, identity.encode("utf-8"), hashlib.sha256).hexdigest()

    return hash_identity
