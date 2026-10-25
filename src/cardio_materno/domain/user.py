"""Usuarios del servicio, sus canales y quién puede escribir en cada chat (HU-09, HU-10).

Un usuario es la persona, independiente del canal. Su identidad en cada canal se guarda
seudonimizada (hash), nunca en claro (Ley 1581/2012).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class Channel(StrEnum):
    """Canal por el que llega un mensaje (ADR 0003)."""

    CONSOLE = "consola"
    WEB = "web"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    HISTORICAL = "historico"


# Chats que la interfaz solo audita: los escribe la persona desde su teléfono, o son
# históricos importados (ADR 0016).
READ_ONLY_CHANNELS = frozenset({Channel.WHATSAPP, Channel.TELEGRAM, Channel.HISTORICAL})
# Canales en los que el equipo puede iniciar un chat directo.
DIRECT_CHANNELS = frozenset({Channel.CONSOLE, Channel.WEB})


class ChatLock(StrEnum):
    """Por qué no se puede escribir en un chat desde la interfaz (ADR 0016)."""

    CHANNEL = "canal_de_solo_lectura"
    LIVE_CONSOLE = "en_uso_en_la_consola"


class ConsentStatus(StrEnum):
    """Estado del consentimiento de tratamiento de datos (HU-01, aún sin implementar)."""

    PENDING = "pendiente"
    ACCEPTED = "aceptado"
    REJECTED = "rechazado"


@dataclass(frozen=True)
class User:
    """Persona que consulta al asistente.

    Attributes:
        id: Identificador interno (no deriva del teléfono ni de otro dato personal).
        created_at: Primer contacto.
        last_seen_at: Último mensaje recibido.
        consent_status: Estado del consentimiento (HU-01).
        live_session_at: Desde cuándo una consola tiene abierto este chat (None si ninguna).
    """

    id: str
    created_at: datetime
    last_seen_at: datetime
    consent_status: ConsentStatus = ConsentStatus.PENDING
    live_session_at: datetime | None = None


def new_user(user_id: str, now: datetime) -> User:
    """Crea un usuario en su primer contacto.

    Args:
        user_id: Identificador interno nuevo.
        now: Momento del primer contacto.

    Returns:
        El usuario con consentimiento pendiente.
    """
    return User(user_id, now, now)


def seen_user(user: User, now: datetime) -> User:
    """Devuelve una copia del usuario con su último contacto actualizado."""
    return replace(user, last_seen_at=now)


def is_idle(last_activity: datetime, now: datetime, timeout: timedelta) -> bool:
    """Indica si un hilo lleva más tiempo sin actividad que el permitido (ADR 0015).

    Args:
        last_activity: Último mensaje o cambio del hilo.
        now: Momento actual.
        timeout: Inactividad máxima antes de cerrar el hilo.

    Returns:
        True si la inactividad supera el límite.
    """
    return now - last_activity > timeout


def chat_lock(channel: Channel, live_session_at: datetime | None) -> ChatLock | None:
    """Indica si la interfaz puede escribir en el chat y, si no, por qué (ADR 0016).

    Args:
        channel: Canal del chat.
        live_session_at: Desde cuándo una consola tiene abierto el chat (None si ninguna).

    Returns:
        None si se puede escribir; si no, el motivo del bloqueo.
    """
    if channel in READ_ONLY_CHANNELS:
        return ChatLock.CHANNEL
    if live_session_at is not None:
        return ChatLock.LIVE_CONSOLE
    return None
