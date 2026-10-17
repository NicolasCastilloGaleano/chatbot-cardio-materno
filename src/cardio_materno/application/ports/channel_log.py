"""Puerto del registro de mensajes de canal: deduplicación y auditoría (ADR 0014 y 0015).

Nunca guarda el texto de los mensajes ni datos personales: solo identificadores,
tipos, estados y tiempos.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from cardio_materno.domain.user import Channel


class InboundStatus(StrEnum):
    """Estado del procesamiento de un mensaje recibido."""

    RECEIVED = "recibido"
    PROCESSING = "procesando"
    ANSWERED = "respondido"
    IGNORED = "ignorado"
    FAILED = "fallido"


class OutboundKind(StrEnum):
    """Tipo de mensaje enviado al usuario."""

    REPLY = "respuesta"
    NOTICE = "aviso"
    ERROR = "error"


@dataclass(frozen=True)
class InboundEvent:
    """Mensaje recibido por un canal.

    Attributes:
        channel: Canal de origen.
        channel_message_id: Identificador que asigna el canal (p. ej., el wamid).
        user_id: Usuario que lo envió.
        kind: Tipo de mensaje del canal (texto, imagen, audio…).
        received_at: Momento de recepción.
    """

    channel: Channel
    channel_message_id: str
    user_id: str
    kind: str
    received_at: datetime


@dataclass(frozen=True)
class OutboundRecord:
    """Mensaje enviado a un usuario.

    Attributes:
        channel: Canal de destino.
        user_id: Usuario destinatario.
        kind: Respuesta, aviso o error.
        channel_message_id: Identificador que devolvió el canal.
        created_at: Momento del envío.
        thread_id: Hilo del turno, si lo hubo.
    """

    channel: Channel
    user_id: str
    kind: OutboundKind
    channel_message_id: str
    created_at: datetime
    thread_id: str | None = None


class ChannelLog(Protocol):
    """Registro de mensajes recibidos y enviados."""

    def register_inbound(self, event: InboundEvent) -> bool:
        """Registra un mensaje recibido.

        Returns:
            False si ya estaba registrado (reenvío del canal); True si es nuevo.
        """
        ...

    def mark_inbound(
        self,
        channel: Channel,
        channel_message_id: str,
        status: InboundStatus,
        error_code: str | None = None,
    ) -> None:
        """Actualiza el estado de un mensaje recibido.

        Raises:
            KeyError: Si el mensaje no está registrado.
        """
        ...

    def record_outbound(self, record: OutboundRecord) -> None:
        """Registra un mensaje enviado."""
        ...
