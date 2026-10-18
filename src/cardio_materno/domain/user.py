"""Usuarios del servicio y sus canales (HU-09, ADR 0015).

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
    """

    id: str
    created_at: datetime
    last_seen_at: datetime
    consent_status: ConsentStatus = ConsentStatus.PENDING


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
