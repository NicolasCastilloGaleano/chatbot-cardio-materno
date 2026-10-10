"""Caso de uso: conversación libre con el modelo de lenguaje (HU-00)."""

from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.domain.conversation import ChatMessage, Role

# Mensajes de usuario y asistente que se conservan como contexto (sin contar el de sistema).
MAX_HISTORY_MESSAGES = 20


class ChatService:
    """Mantiene el historial de una sesión y obtiene respuestas del modelo.

    El historial vive en memoria: cada instancia representa una sola conversación.
    """

    def __init__(
        self,
        language_model: LanguageModel,
        system_prompt: str,
        max_history: int = MAX_HISTORY_MESSAGES,
    ) -> None:
        """Crea el servicio.

        Args:
            language_model: Implementación del puerto de LLM.
            system_prompt: Instrucciones de sistema que encabezan cada llamada.
            max_history: Máximo de mensajes previos que se envían como contexto.
        """
        self._language_model = language_model
        self._system_message = ChatMessage(Role.SYSTEM, system_prompt)
        self._max_history = max_history
        self._history: list[ChatMessage] = []

    def send(self, user_text: str) -> str:
        """Envía un mensaje del usuario y devuelve la respuesta del asistente.

        Si el modelo falla, el mensaje del usuario no queda en el historial.

        Args:
            user_text: Texto escrito por el usuario.

        Returns:
            Respuesta del asistente.

        Raises:
            LanguageModelError: Si el modelo no pudo responder.
        """
        user_message = ChatMessage(Role.USER, user_text)
        answer = self._language_model.reply(self._build_context(user_message))
        self._remember(user_message, ChatMessage(Role.ASSISTANT, answer))
        return answer

    def _build_context(self, user_message: ChatMessage) -> list[ChatMessage]:
        """Arma la conversación que se envía al modelo: sistema + historial + mensaje nuevo."""
        return [self._system_message, *self._history, user_message]

    def _remember(self, *messages: ChatMessage) -> None:
        """Agrega mensajes al historial y descarta los más antiguos si se supera el límite."""
        self._history.extend(messages)
        self._history = self._history[-self._max_history :]
