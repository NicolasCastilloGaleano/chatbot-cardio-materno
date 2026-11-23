"""Consentimiento informado antes de atender (HU-01, Ley 1581/2012).

La respuesta de la persona se lee con una regla determinista y estricta: solo un "sí" o un
"no" claros cambian el estado. Cualquier otro mensaje vuelve a mostrar la solicitud, de
modo que nunca se atiende ni se guarda una consulta sin aceptación.
"""

from dataclasses import replace
from datetime import datetime
from enum import StrEnum

from cardio_materno.domain.alarms import normalize_text
from cardio_materno.domain.user import ConsentStatus, User

# Frases ya normalizadas: minúsculas y sin tildes (la ñ queda como n).
ACCEPT_PHRASES = frozenset(
    {
        "si", "si acepto", "acepto", "yo acepto", "de acuerdo", "estoy de acuerdo",
        "si estoy de acuerdo", "si senor", "si senora", "si claro", "claro que si", "ok",
        "okay", "listo", "dale", "bueno",
    }
)  # fmt: skip
REJECT_PHRASES = frozenset(
    {"no", "no acepto", "no gracias", "no estoy de acuerdo", "rechazo", "no quiero"}
)
PUNCTUATION = str.maketrans("", "", ".,;:!¡?¿\"'()")


class ConsentAnswer(StrEnum):
    """Lo que la persona respondió a la solicitud de consentimiento."""

    ACCEPT = "acepta"
    REJECT = "rechaza"
    UNCLEAR = "no_claro"


def read_consent_answer(text: str) -> ConsentAnswer:
    """Interpreta la respuesta a la solicitud de consentimiento.

    Args:
        text: Mensaje de la persona.

    Returns:
        ACCEPT o REJECT solo si el mensaje completo es una aceptación o un rechazo claros;
        UNCLEAR en cualquier otro caso (p. ej., "sí, pero me duele el pecho").
    """
    plain = normalize_text(text.translate(PUNCTUATION))
    if plain in ACCEPT_PHRASES:
        return ConsentAnswer.ACCEPT
    if plain in REJECT_PHRASES:
        return ConsentAnswer.REJECT
    return ConsentAnswer.UNCLEAR


def has_consented(user: User) -> bool:
    """Indica si la persona aceptó el tratamiento de sus datos."""
    return user.consent_status is ConsentStatus.ACCEPTED


def with_consent_decision(user: User, accepted: bool, now: datetime) -> User:
    """Devuelve el usuario con su decisión de consentimiento y el momento en que la tomó.

    Rechazar (o retirar) el consentimiento retira también la autorización para informes:
    no puede quedar un uso secundario de los datos de quien ya no acepta el uso principal.
    """
    if accepted:
        return replace(user, consent_status=ConsentStatus.ACCEPTED, consent_at=now)
    rejected = replace(user, consent_status=ConsentStatus.REJECTED, consent_at=now)
    if rejected.research_consent is ConsentStatus.ACCEPTED:
        return with_research_decision(rejected, False, now)
    return rejected


def authorizes_research(user: User) -> bool:
    """Indica si la persona autorizó usar sus datos de acceso en informes agregados.

    Es una autorización distinta del consentimiento para ser atendida (ADR 0023): quien no
    la da recibe la misma atención y sus datos codificados no se guardan. Nunca vale si la
    persona rechazó el consentimiento para ser atendida.
    """
    refused = user.consent_status is ConsentStatus.REJECTED
    return user.research_consent is ConsentStatus.ACCEPTED and not refused


def with_research_decision(user: User, accepted: bool, now: datetime) -> User:
    """Devuelve el usuario con su decisión sobre los informes agregados y su fecha."""
    status = ConsentStatus.ACCEPTED if accepted else ConsentStatus.REJECTED
    return replace(user, research_consent=status, research_at=now)
