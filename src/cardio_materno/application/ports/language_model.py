"""Puerto del modelo de lenguaje."""

from collections.abc import Sequence
from typing import Any, Protocol

from cardio_materno.domain.conversation import ChatMessage


class LanguageModel(Protocol):
    """Genera la siguiente respuesta del asistente a partir de la conversación."""

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Devuelve la respuesta del modelo como un objeto JSON que sigue el esquema.

        Args:
            messages: Conversación a enviar, empezando por los mensajes de sistema.
            schema: JSON Schema que debe cumplir la respuesta.

        Returns:
            El objeto JSON devuelto por el modelo (la validación de negocio la hace la aplicación).

        Raises:
            LanguageModelError: Si el modelo no está disponible, falla o no devuelve JSON.
        """
        ...
