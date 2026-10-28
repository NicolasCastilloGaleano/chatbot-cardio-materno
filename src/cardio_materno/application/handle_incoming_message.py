"""Caso de uso: atender un mensaje de un canal de chat continuo (HU-09, ADR 0014 y 0015).

El agente no cambia: por cada mensaje se crea un `ConversationService` con el repositorio
acotado al usuario y su hilo abierto, así que recibe el mismo contexto que en la consola.
Este caso de uso solo añade lo propio del canal: usuario, deduplicación, aviso de espera,
división de respuestas largas y registro de lo enviado. El cierre por inactividad lo aplica
`UserConversations`, común a todos los canales.
"""

import logging
from dataclasses import dataclass

from cardio_materno.application.channel_messages import (
    MODEL_ERROR_TEXT,
    UNSUPPORTED_MESSAGE_TEXT,
    WAIT_NOTICE_TEXT,
    WHATSAPP_MAX_CHARS,
    split_message,
)
from cardio_materno.application.conversation_service import (
    Clock,
    IdGenerator,
    TurnResult,
    new_uuid,
    utc_now,
)
from cardio_materno.application.errors import ChannelDeliveryError, LanguageModelError
from cardio_materno.application.incoming_message import IncomingMessage, MessageKind
from cardio_materno.application.ports.channel_log import (
    ChannelLog,
    InboundEvent,
    InboundStatus,
    OutboundKind,
    OutboundRecord,
)
from cardio_materno.application.ports.message_sender import DelayedActions, MessageSender
from cardio_materno.application.ports.user_directory import UserDirectory
from cardio_materno.application.user_conversations import UserConversations
from cardio_materno.domain.user import new_user, seen_user

ERROR_MODEL = "modelo"
ERROR_DELIVERY = "envio"

logger = logging.getLogger(__name__)
# Etapa y causa técnica del fallo del modelo; nunca el texto ni la identidad de la persona.
MODEL_FAILURE_LOG = "Fallo del modelo (etapa: %s): %s"
UNKNOWN_STAGE = "desconocida"


@dataclass(frozen=True)
class ChannelPorts:
    """Puertos que necesita el caso de uso.

    Attributes:
        users: Directorio de usuarios.
        log: Registro de mensajes recibidos y enviados.
        sender: Envío por el canal.
        delayed: Programación del aviso de espera.
    """

    users: UserDirectory
    log: ChannelLog
    sender: MessageSender
    delayed: DelayedActions


@dataclass(frozen=True)
class ChannelConfig:
    """Configuración del canal.

    Attributes:
        wait_notice_seconds: Espera antes de enviar el aviso de "estoy revisando".
        max_message_chars: Máximo de caracteres por mensaje del canal.
        clock: Reloj (UTC).
        new_id: Generador de identificadores de usuario.
    """

    wait_notice_seconds: float
    max_message_chars: int = WHATSAPP_MAX_CHARS
    clock: Clock = utc_now
    new_id: IdGenerator = new_uuid


class HandleIncomingMessage:
    """Atiende un mensaje de un canal y responde por el mismo canal."""

    def __init__(
        self, ports: ChannelPorts, config: ChannelConfig, conversations: UserConversations
    ) -> None:
        """Crea el caso de uso.

        Args:
            ports: Usuarios, registro, envío y aviso de espera.
            config: Aviso, tamaño de mensaje, reloj e ids.
            conversations: Servicio conversacional de cada usuario (con la regla de
                inactividad).
        """
        self._ports = ports
        self._config = config
        self._conversations = conversations

    def handle(self, message: IncomingMessage) -> None:
        """Procesa el mensaje; un reenvío del canal (mismo identificador) se ignora.

        Raises:
            ChannelDeliveryError: Si no se pudo entregar la respuesta (queda "fallido").
        """
        user_id = self._resolve_user(message)
        if not self._register(message, user_id):
            return
        try:
            self._attend(message, user_id)
        except ChannelDeliveryError:
            self._mark(message, InboundStatus.FAILED, ERROR_DELIVERY)
            raise

    def _attend(self, message: IncomingMessage, user_id: str) -> None:
        """Acusa recibo y responde según el tipo de mensaje."""
        self._acknowledge(message)
        if message.kind is MessageKind.UNSUPPORTED:
            self._deliver(message, user_id, UNSUPPORTED_MESSAGE_TEXT, OutboundKind.NOTICE)
            self._mark(message, InboundStatus.IGNORED)
            return
        self._mark(message, InboundStatus.PROCESSING)
        result = self._converse(message, user_id)
        if result is None:
            self._deliver(message, user_id, MODEL_ERROR_TEXT, OutboundKind.ERROR)
            self._mark(message, InboundStatus.FAILED, ERROR_MODEL)
            return
        self._deliver_reply(message, user_id, result)
        self._mark(message, InboundStatus.ANSWERED)

    def _converse(self, message: IncomingMessage, user_id: str) -> TurnResult | None:
        """Llama al agente con el aviso de espera programado; None si el modelo falló."""
        service = self._conversations.service_for(user_id)
        cancel = self._ports.delayed.schedule(
            self._config.wait_notice_seconds, lambda: self._notify_wait(message, user_id)
        )
        try:
            return service.send(message.text)
        except LanguageModelError as error:
            logger.warning(MODEL_FAILURE_LOG, error.stage or UNKNOWN_STAGE, error)
            return None
        finally:
            cancel()

    def _resolve_user(self, message: IncomingMessage) -> str:
        """Busca al usuario de la identidad del canal o lo crea en su primer contacto."""
        now = self._config.clock()
        users = self._ports.users
        user = users.find(message.channel, message.user_hash)
        if user is None:
            user = new_user(self._config.new_id(), now)
            users.register(user, message.channel, message.user_hash)
        else:
            users.save(seen_user(user, now))
        return user.id

    def _register(self, message: IncomingMessage, user_id: str) -> bool:
        """Registra el mensaje; False si el canal ya lo había enviado antes."""
        event = InboundEvent(
            message.channel,
            message.channel_message_id,
            user_id,
            message.channel_kind,
            self._config.clock(),
        )
        return self._ports.log.register_inbound(event)

    def _acknowledge(self, message: IncomingMessage) -> None:
        """Marca como leído con "escribiendo…"; si falla, igual se responde."""
        try:
            self._ports.sender.acknowledge(message.reply_to, message.channel_message_id)
        except ChannelDeliveryError as error:
            logger.warning("No se pudo marcar el mensaje como leído: %s", error)

    def _notify_wait(self, message: IncomingMessage, user_id: str) -> None:
        """Envía el aviso de espera (se ejecuta en otro hilo; un fallo no detiene el turno)."""
        try:
            self._deliver(message, user_id, WAIT_NOTICE_TEXT, OutboundKind.NOTICE)
        except ChannelDeliveryError as error:
            logger.warning("No se pudo enviar el aviso de espera: %s", error)

    def _deliver_reply(self, message: IncomingMessage, user_id: str, result: TurnResult) -> None:
        """Envía la respuesta en las partes que hagan falta."""
        thread_id = result.thread.id if result.thread is not None else None
        for part in split_message(result.reply, self._config.max_message_chars):
            self._deliver(message, user_id, part, OutboundKind.REPLY, thread_id)

    def _deliver(
        self,
        message: IncomingMessage,
        user_id: str,
        text: str,
        kind: OutboundKind,
        thread_id: str | None = None,
    ) -> None:
        """Envía un mensaje y lo registra (sin su texto)."""
        sent_id = self._ports.sender.send_text(message.reply_to, text)
        record = OutboundRecord(
            message.channel, user_id, kind, sent_id, self._config.clock(), thread_id
        )
        self._ports.log.record_outbound(record)

    def _mark(
        self, message: IncomingMessage, status: InboundStatus, error_code: str | None = None
    ) -> None:
        """Actualiza el estado del mensaje recibido."""
        self._ports.log.mark_inbound(
            message.channel, message.channel_message_id, status, error_code
        )
