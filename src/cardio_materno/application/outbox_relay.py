"""Reenvío por WhatsApp de los mensajes del profesional (HU-16, ADR 0022 y 0023).

Corre en el proceso de WhatsApp, cada pocos segundos. Toma lo que el profesional dejó en la
bandeja de salida y lo envía por el número del proyecto, con la etiqueta "Profesional de
salud": así la persona sabe quién le escribe y el teléfono del profesional nunca se expone.
"""

import logging

from cardio_materno.application.channel_messages import WHATSAPP_MAX_CHARS, split_message
from cardio_materno.application.conversation_service import Clock, utc_now
from cardio_materno.application.errors import ChannelDeliveryError
from cardio_materno.application.ports.channel_log import ChannelLog, OutboundKind, OutboundRecord
from cardio_materno.application.ports.clinician_outbox import (
    OutboxItem,
    OutboxQueue,
    OutboxStatus,
)
from cardio_materno.application.ports.message_sender import MessageSender
from cardio_materno.domain.user import Channel

CLINICIAN_LABEL = "*Profesional de salud:*"
ERROR_NO_ADDRESS = "sin_direccion"
ERROR_DELIVERY = "envio"

logger = logging.getLogger(__name__)


class OutboxRelay:
    """Envía los mensajes pendientes del profesional y borra las direcciones vencidas."""

    def __init__(
        self,
        queue: OutboxQueue,
        sender: MessageSender,
        log: ChannelLog,
        max_chars: int = WHATSAPP_MAX_CHARS,
        clock: Clock = utc_now,
    ) -> None:
        """Crea el reenvío.

        Args:
            queue: Bandeja de salida y direcciones.
            sender: Envío por WhatsApp.
            log: Registro de lo enviado (sin el texto).
            max_chars: Máximo de caracteres por mensaje.
            clock: Reloj (UTC).
        """
        self._queue = queue
        self._sender = sender
        self._log = log
        self._max_chars = max_chars
        self._clock = clock

    def run_once(self) -> int:
        """Una vuelta: vence lo que pasó de la ventana, envía lo pendiente y purga.

        Returns:
            Cuántos mensajes se enviaron.
        """
        self._queue.purge(self._clock())
        sent = sum(self._send(item) for item in self._queue.claim(self._clock()))
        self._queue.purge(self._clock())
        return sent

    def _send(self, item: OutboxItem) -> bool:
        """Envía un mensaje en las partes que hagan falta; True si salió completo."""
        reply_to = self._queue.address_of(item.case_id)
        if reply_to is None:
            self._queue.finish(item.id, OutboxStatus.FAILED, self._clock(), ERROR_NO_ADDRESS)
            return False
        try:
            for part in split_message(f"{CLINICIAN_LABEL} {item.text}", self._max_chars):
                self._deliver(item, reply_to, part)
        except ChannelDeliveryError as error:
            logger.warning("No se pudo reenviar un mensaje del profesional: %s", error)
            self._queue.finish(item.id, OutboxStatus.FAILED, self._clock(), ERROR_DELIVERY)
            return False
        self._queue.finish(item.id, OutboxStatus.SENT, self._clock())
        return True

    def _deliver(self, item: OutboxItem, reply_to: str, text: str) -> None:
        """Envía una parte y la registra."""
        sent_id = self._sender.send_text(reply_to, text)
        record = OutboundRecord(
            Channel.WHATSAPP,
            item.user_id,
            OutboundKind.CLINICIAN,
            sent_id,
            self._clock(),
            item.thread_id,
        )
        self._log.record_outbound(record)
