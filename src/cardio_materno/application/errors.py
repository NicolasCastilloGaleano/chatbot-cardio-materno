"""Excepciones de la capa de aplicación."""


class LanguageModelError(Exception):
    """El modelo de lenguaje no pudo generar una respuesta.

    El mensaje de la excepción está en español y es apto para mostrarse al usuario
    del equipo (explica la causa y, si se conoce, cómo solucionarla).
    """
