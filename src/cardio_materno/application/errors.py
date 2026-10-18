"""Excepciones de la capa de aplicación."""


class LanguageModelError(Exception):
    """El modelo de lenguaje no pudo generar una respuesta.

    El mensaje de la excepción está en español y es apto para mostrarse al usuario
    del equipo (explica la causa y, si se conoce, cómo solucionarla).
    """


class ChannelDeliveryError(Exception):
    """El canal (p. ej., WhatsApp) no aceptó o no recibió un envío.

    El mensaje explica la causa técnica sin incluir el texto ni la identidad del usuario.
    """
