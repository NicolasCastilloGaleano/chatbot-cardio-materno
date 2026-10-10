"""Entidades básicas de una conversación."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    """Autor de un mensaje dentro de la conversación."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """Mensaje inmutable de la conversación.

    Attributes:
        role: Quién escribió el mensaje.
        content: Texto del mensaje.
    """

    role: Role
    content: str
