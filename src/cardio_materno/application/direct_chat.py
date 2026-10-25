"""Caso de uso: chat directo de consola y web, como un chat continuo por usuario (HU-10, ADR 0016).

Cada arranque de la consola y cada "Nueva sesión" de la web crean un usuario con su chat.
Mientras una consola está abierta, su chat queda marcado y la web no puede escribir en él.
Cada turno usa `UserConversations`, así que el agente recibe el mismo contexto que en
WhatsApp y se aplica la misma regla de inactividad.
"""

import secrets
from collections.abc import Callable
from dataclasses import replace

from cardio_materno.application.conversation_service import (
    Clock,
    IdGenerator,
    TurnResult,
    new_uuid,
    utc_now,
)
from cardio_materno.application.errors import ChatNotFoundError, ChatReadOnlyError
from cardio_materno.application.ports.user_directory import ChatOwner, UserDirectory
from cardio_materno.application.user_conversations import UserConversations
from cardio_materno.domain.user import (
    DIRECT_CHANNELS,
    Channel,
    ChatLock,
    chat_lock,
    new_user,
    seen_user,
)

TOKEN_BYTES = 16
TokenGenerator = Callable[[], str]


def new_token() -> str:
    """Identidad de canal aleatoria para consola y web (no deriva de ningún dato personal)."""
    return secrets.token_hex(TOKEN_BYTES)


class DirectChat:
    """Crea chats de consola o web y procesa sus turnos."""

    def __init__(
        self,
        users: UserDirectory,
        conversations: UserConversations,
        clock: Clock = utc_now,
        new_id: IdGenerator = new_uuid,
        token: TokenGenerator = new_token,
    ) -> None:
        """Crea el caso de uso.

        Args:
            users: Directorio de usuarios.
            conversations: Servicio conversacional de cada usuario.
            clock: Reloj (UTC).
            new_id: Generador de identificadores de usuario.
            token: Generador de la identidad de canal.
        """
        self._users = users
        self._conversations = conversations
        self._clock = clock
        self._new_id = new_id
        self._token = token

    def start(self, channel: Channel) -> str:
        """Crea un chat nuevo de consola o web.

        Returns:
            El identificador del chat (el del usuario).

        Raises:
            ValueError: Si el canal no admite chats directos (p. ej., WhatsApp).
        """
        if channel not in DIRECT_CHANNELS:
            raise ValueError(f"El canal {channel} no admite chats directos")
        user = new_user(self._new_id(), self._clock())
        self._users.register(user, channel, self._token())
        return user.id

    def send(self, user_id: str, text: str, from_console: bool = False) -> TurnResult:
        """Procesa un mensaje en el chat.

        Args:
            user_id: Chat en el que se escribe.
            text: Mensaje.
            from_console: True si lo envía la consola que tiene abierto el chat.

        Raises:
            ChatNotFoundError: Si el chat no existe.
            ChatReadOnlyError: Si el canal es de solo lectura o una consola tiene abierto
                el chat (y el mensaje no viene de ella).
            LanguageModelError: Si el modelo falla y no hay alarma.
        """
        owner = self._owner(user_id)
        lock = chat_lock(owner.channel, owner.user.live_session_at)
        if lock is not None and not (from_console and lock is ChatLock.LIVE_CONSOLE):
            raise ChatReadOnlyError(lock)
        self._users.save(seen_user(owner.user, self._clock()))
        return self._conversations.service_for(user_id).send(text)

    def end(self, user_id: str) -> None:
        """Cierra el hilo abierto del chat (p. ej., al escribir "salir" en la consola)."""
        self._conversations.close_open_thread(user_id)

    def claim_console(self, user_id: str) -> None:
        """Marca el chat como abierto en una consola: la web no podrá escribir en él."""
        owner = self._owner(user_id)
        self._users.save(replace(owner.user, live_session_at=self._clock()))

    def release_console(self, user_id: str) -> None:
        """Libera el chat de la consola (al salir, o desde la web tras un cierre abrupto)."""
        owner = self._owner(user_id)
        self._users.save(replace(owner.user, live_session_at=None))

    def _owner(self, user_id: str) -> ChatOwner:
        """Dueño del chat.

        Raises:
            ChatNotFoundError: Si no existe.
        """
        owner = self._users.get(user_id)
        if owner is None:
            raise ChatNotFoundError(user_id)
        return owner


class ConsoleChatSession:
    """Sesión de consola sobre un chat directo: la interfaz que usa `ConsoleChat`."""

    def __init__(self, chat: DirectChat, user_id: str) -> None:
        """Crea la sesión.

        Args:
            chat: Caso de uso del chat directo.
            user_id: Chat que abrió la consola.
        """
        self._chat = chat
        self.user_id = user_id

    def send(self, user_text: str) -> TurnResult:
        """Procesa un mensaje escrito en la consola."""
        return self._chat.send(self.user_id, user_text, from_console=True)

    def end_session(self) -> None:
        """Cierra el hilo abierto y libera el chat para continuarlo en la web."""
        self._chat.end(self.user_id)
        self._chat.release_console(self.user_id)


def open_console_session(chat: DirectChat) -> ConsoleChatSession:
    """Crea el chat de una consola que arranca y lo marca como abierto en ella."""
    user_id = chat.start(Channel.CONSOLE)
    chat.claim_console(user_id)
    return ConsoleChatSession(chat, user_id)
