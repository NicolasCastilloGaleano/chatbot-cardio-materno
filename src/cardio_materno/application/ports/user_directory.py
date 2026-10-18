"""Puerto del directorio de usuarios y sus identidades de canal (ADR 0015)."""

from dataclasses import dataclass
from typing import Protocol

from cardio_materno.domain.user import Channel, User


@dataclass(frozen=True)
class ChatOwner:
    """Usuario dueño de un chat y el canal por el que conversa.

    Attributes:
        user: El usuario.
        channel: Canal de su chat (el de su primera identidad).
    """

    user: User
    channel: Channel


class UserDirectory(Protocol):
    """Guarda usuarios y los liga con su identidad seudonimizada en cada canal."""

    def get(self, user_id: str) -> ChatOwner | None:
        """Devuelve el usuario con el canal de su chat, o None si no existe."""
        ...

    def find(self, channel: Channel, user_hash: str) -> User | None:
        """Busca al usuario de una identidad de canal.

        Args:
            channel: Canal de la identidad.
            user_hash: Hash de la identidad (nunca el dato en claro).

        Returns:
            El usuario, o None si la identidad no está registrada.
        """
        ...

    def register(self, user: User, channel: Channel, user_hash: str) -> None:
        """Crea el usuario y lo liga con su identidad de canal.

        Raises:
            ValueError: Si la identidad ya está ligada a un usuario.
        """
        ...

    def save(self, user: User) -> None:
        """Actualiza los datos del usuario (último contacto, consentimiento, uso en consola).

        Raises:
            KeyError: Si el usuario no existe.
        """
        ...
