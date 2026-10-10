"""Puerto del modelo de lenguaje."""

from collections.abc import Sequence
from typing import Protocol

from cardio_materno.domain.conversation import ChatMessage


class LanguageModel(Protocol):
    """Genera la siguiente respuesta del asistente a partir de la conversación."""

    def reply(self, messages: Sequence[ChatMessage]) -> str:
        """Devuelve la respuesta del asistente.

        Args:
            messages: Conversación completa, empezando por el mensaje de sistema.

        Returns:
            Texto de la respuesta, sin espacios al inicio ni al final.

        Raises:
            LanguageModelError: Si el modelo no está disponible o falla.
        """
        ...
