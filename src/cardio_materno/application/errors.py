"""Excepciones de la capa de aplicación."""


class LanguageModelError(Exception):
    """El modelo de lenguaje no pudo generar una respuesta.

    El mensaje de la excepción está en español y es apto para mostrarse al usuario
    del equipo (explica la causa y, si se conoce, cómo solucionarla).
    """


class ChatNotFoundError(Exception):
    """No existe un chat (usuario) con ese identificador."""


class ChatReadOnlyError(Exception):
    """No se puede escribir en el chat desde la interfaz (ADR 0016).

    Attributes:
        reason: Motivo del bloqueo (`ChatLock`): canal de solo lectura o consola abierta.
    """

    def __init__(self, reason: str) -> None:
        """Crea el error con el motivo del bloqueo."""
        super().__init__(reason)
        self.reason = reason


class ChannelDeliveryError(Exception):
    """El canal (p. ej., WhatsApp) no aceptó o no recibió un envío.

    El mensaje explica la causa técnica sin incluir el texto ni la identidad del usuario.
    """
