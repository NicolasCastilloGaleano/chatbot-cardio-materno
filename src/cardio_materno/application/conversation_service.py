"""Caso de uso: conversación organizada en hilos con resumen (HU-06, ADR 0006).

En cada turno se envía al agente solo el contexto del hilo actual (su JSON y sus
últimos N mensajes). El agente responde en JSON, decide si el mensaje continúa el
hilo o abre uno nuevo y actualiza el resumen y el dominio.
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from cardio_materno.application.agent_turn import (
    AGENT_TURN_SCHEMA,
    AgentTurn,
    ThreadAction,
    parse_agent_turn,
)
from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.domain.conversation import (
    ChatMessage,
    ConversationThread,
    Role,
    close_thread,
    open_thread,
    update_thread,
)

# Mensajes del hilo actual que se envían como contexto (3 turnos de pregunta y respuesta).
DEFAULT_CONTEXT_MESSAGES = 6
THREAD_CONTEXT_TEMPLATE = "HILO ACTUAL (JSON):\n{thread_json}"
NO_THREAD_CONTEXT = "HILO ACTUAL: no hay un hilo activo. Este mensaje inicia un hilo nuevo."

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def utc_now() -> datetime:
    """Devuelve la fecha y hora actual en UTC."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Genera un identificador único aleatorio."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class TurnResult:
    """Resultado de un turno de conversación.

    Attributes:
        reply: Respuesta para el usuario.
        thread: Hilo en el que quedó registrado el turno.
        is_new_thread: True si el turno abrió un hilo nuevo.
    """

    reply: str
    thread: ConversationThread
    is_new_thread: bool


@dataclass(frozen=True)
class ConversationConfig:
    """Parámetros del caso de uso (agrupados para mantener constructores pequeños).

    Attributes:
        system_prompt: Instrucciones de sistema del agente.
        context_messages: Cuántos mensajes recientes del hilo se envían como contexto.
        clock: Fuente de la fecha y hora (se reemplaza en las pruebas).
        new_id: Generador de identificadores de hilo (se reemplaza en las pruebas).
    """

    system_prompt: str
    context_messages: int = DEFAULT_CONTEXT_MESSAGES
    clock: Clock = utc_now
    new_id: IdGenerator = new_uuid


class ConversationService:
    """Coordina el agente y el repositorio de hilos para una sesión de un usuario."""

    def __init__(
        self,
        language_model: LanguageModel,
        repository: ThreadRepository,
        config: ConversationConfig,
    ) -> None:
        """Crea el servicio.

        Args:
            language_model: Implementación del puerto de LLM.
            repository: Implementación del repositorio de hilos.
            config: Prompt de sistema, tamaño del contexto, reloj y generador de ids.
        """
        self._language_model = language_model
        self._repository = repository
        self._system_message = ChatMessage(Role.SYSTEM, config.system_prompt)
        self._context_messages = config.context_messages
        self._clock = config.clock
        self._new_id = config.new_id
        self._active_thread_id: str | None = None

    def send(self, user_text: str) -> TurnResult:
        """Procesa un mensaje del usuario y devuelve la respuesta del agente.

        Si el modelo falla, no se guarda nada y el hilo activo no cambia.

        Args:
            user_text: Texto escrito por el usuario.

        Returns:
            La respuesta y el hilo en el que quedó el turno.

        Raises:
            LanguageModelError: Si el modelo falla o no devuelve la estructura esperada.
        """
        current = self._active_thread()
        context = self._build_context(current, user_text)
        turn = parse_agent_turn(self._language_model.complete_json(context, AGENT_TURN_SCHEMA))
        thread, is_new = self._resolve_thread(current, turn)
        self._record_turn(thread.id, user_text, turn.reply)
        return TurnResult(turn.reply, thread, is_new)

    def end_session(self) -> None:
        """Cierra el hilo activo, si existe (p. ej., cuando el usuario escribe "salir")."""
        current = self._active_thread()
        if current is not None:
            self._repository.save_thread(close_thread(current, self._clock()))
        self._active_thread_id = None

    def _active_thread(self) -> ConversationThread | None:
        """Obtiene el hilo activo de la sesión, si lo hay y sigue abierto."""
        if self._active_thread_id is None:
            return None
        thread = self._repository.get_thread(self._active_thread_id)
        return thread if thread is not None and thread.is_open else None

    def _build_context(
        self, current: ConversationThread | None, user_text: str
    ) -> list[ChatMessage]:
        """Arma el contexto: sistema + JSON del hilo + últimos N mensajes + mensaje nuevo."""
        recent = (
            self._repository.recent_messages(current.id, self._context_messages) if current else []
        )
        return [
            self._system_message,
            ChatMessage(Role.SYSTEM, describe_thread(current)),
            *recent,
            ChatMessage(Role.USER, user_text),
        ]

    def _resolve_thread(
        self, current: ConversationThread | None, turn: AgentTurn
    ) -> tuple[ConversationThread, bool]:
        """Aplica la decisión del agente: actualiza el hilo actual o lo cierra y abre otro."""
        now = self._clock()
        if current is not None and turn.thread_action is ThreadAction.CONTINUE:
            thread = update_thread(current, turn.domain, turn.summary, now)
            self._repository.save_thread(thread)
            return thread, False
        if current is not None:
            self._repository.save_thread(close_thread(current, now))
        thread = open_thread(self._new_id(), turn.domain, turn.summary, now)
        self._repository.save_thread(thread)
        self._active_thread_id = thread.id
        return thread, True

    def _record_turn(self, thread_id: str, user_text: str, reply: str) -> None:
        """Guarda el mensaje del usuario y la respuesta con el identificador del hilo."""
        now = self._clock()
        self._repository.append_message(ChatMessage(Role.USER, user_text, thread_id, now))
        self._repository.append_message(ChatMessage(Role.ASSISTANT, reply, thread_id, now))


def describe_thread(thread: ConversationThread | None) -> str:
    """Describe el hilo actual para el agente, en JSON (o indica que no hay hilo).

    Args:
        thread: Hilo activo o None.

    Returns:
        Texto que se envía al agente como mensaje de sistema.
    """
    if thread is None:
        return NO_THREAD_CONTEXT
    snapshot = {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
    }
    return THREAD_CONTEXT_TEMPLATE.format(thread_json=json.dumps(snapshot, ensure_ascii=False))
