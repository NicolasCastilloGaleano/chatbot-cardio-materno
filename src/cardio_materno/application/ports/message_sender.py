"""Puerto para enviar mensajes al usuario por su canal (ADR 0014).

Es el `MessageChannel` previsto en la arquitectura, del lado de salida.
"""

from collections.abc import Callable
from typing import Protocol

CancelAction = Callable[[], None]


class MessageSender(Protocol):
    """Entrega mensajes de texto e indicadores de lectura en un canal."""

    def send_text(self, reply_to: str, text: str) -> str:
        """Envía un mensaje de texto.

        Args:
            reply_to: Dirección del destinatario en el canal.
            text: Texto que cabe en un mensaje del canal.

        Returns:
            Identificador del mensaje enviado que devuelve el canal.

        Raises:
            ChannelDeliveryError: Si el canal rechaza o no recibe el envío.
        """
        ...

    def acknowledge(self, reply_to: str, channel_message_id: str) -> None:
        """Marca el mensaje como leído y muestra que se está escribiendo.

        Raises:
            ChannelDeliveryError: Si el canal rechaza la solicitud.
        """
        ...


class DelayedActions(Protocol):
    """Programa una acción para dentro de unos segundos (aviso de espera)."""

    def schedule(self, delay_seconds: float, action: Callable[[], None]) -> CancelAction:
        """Ejecuta `action` tras `delay_seconds`, salvo que se cancele antes.

        Returns:
            Función que cancela la acción si aún no se ejecutó.
        """
        ...
