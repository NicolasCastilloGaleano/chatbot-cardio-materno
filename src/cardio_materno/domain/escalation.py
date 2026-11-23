"""Caso escalado a un profesional de salud cuando no hay evidencia (HU-16, ADR 0022).

Reglas puras: estados del caso, transiciones permitidas y vencimiento. Un caso abierto
(`pendiente` o `en_contacto`) vence a las 24 h del último mensaje de la persona, porque
WhatsApp solo permite mensajes libres dentro de esa ventana (ADR 0023).
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from cardio_materno.domain.conversation import Domain


class CaseStatus(StrEnum):
    """Estado de un caso escalado."""

    PENDING = "pendiente"
    IN_CONTACT = "en_contacto"
    APPROVED = "aprobada"
    MODIFIED = "modificada"
    CLOSED = "cerrada"
    EXPIRED = "expirada"


class DraftStatus(StrEnum):
    """Estado del borrador que ve el profesional (marcado "sin respaldo de la base")."""

    NOT_READY = "sin_generar"
    READY = "listo"
    FAILED = "fallido"


class CaseAction(StrEnum):
    """Lo que puede hacer el profesional con un caso, o el vencimiento."""

    APPROVE = "aprobar"
    MODIFY = "modificar"
    START_CONTACT = "contacto_directo"
    CLOSE = "cerrar"
    EXPIRE = "vencer"


OPEN_STATUSES = frozenset({CaseStatus.PENDING, CaseStatus.IN_CONTACT})
TRANSITIONS: dict[tuple[CaseStatus, CaseAction], CaseStatus] = {
    (CaseStatus.PENDING, CaseAction.APPROVE): CaseStatus.APPROVED,
    (CaseStatus.PENDING, CaseAction.MODIFY): CaseStatus.MODIFIED,
    (CaseStatus.PENDING, CaseAction.START_CONTACT): CaseStatus.IN_CONTACT,
    (CaseStatus.PENDING, CaseAction.EXPIRE): CaseStatus.EXPIRED,
    (CaseStatus.IN_CONTACT, CaseAction.CLOSE): CaseStatus.CLOSED,
    (CaseStatus.IN_CONTACT, CaseAction.EXPIRE): CaseStatus.EXPIRED,
}


class InvalidCaseTransitionError(ValueError):
    """La acción no se puede aplicar al caso en su estado actual."""


@dataclass(frozen=True)
class CaseSnapshot:
    """Resumen clínico del caso, sin datos de identificación (lo que ya guarda la traza).

    Attributes:
        domain: Dominio de la consulta.
        summary: Resumen del hilo que escribió el análisis.
        symptoms: Síntomas que reporta la persona.
        signs: Códigos de signos del catálogo (ADR 0012).
        query: Consulta de búsqueda que reformuló el análisis.
        reason: Por qué no hubo orientación (vacío de la HU-15).
        category: Categoría de la base más cercana.
        best_score: Mejor similitud encontrada.
    """

    domain: Domain
    summary: str
    symptoms: tuple[str, ...]
    signs: tuple[str, ...]
    query: str
    reason: str
    category: str
    best_score: float


@dataclass(frozen=True)
class ClinicalCase:
    """Consulta sin evidencia que espera a un profesional de salud.

    Attributes:
        id: Identificador del caso.
        thread_id: Hilo en el que se abrió.
        snapshot: Resumen clínico al abrirse.
        status: Estado actual.
        notified: True si la persona recibió el aviso de espera (modo `activo`); False si el
            caso solo se observa.
        gap_count: Turnos sin evidencia que sumó el caso.
        created_at: Apertura.
        expires_at: Vencimiento: la ventana desde el último mensaje de la persona.
        closed_at: Cierre, aprobación, modificación o vencimiento (None si sigue abierto).
        draft: Borrador de respuesta del modelo, sin respaldo de la base ("" si no hay).
        draft_status: Si el borrador está por generar, listo o falló.
    """

    id: str
    thread_id: str
    snapshot: CaseSnapshot
    status: CaseStatus
    notified: bool
    gap_count: int
    created_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None
    draft: str = ""
    draft_status: DraftStatus = DraftStatus.NOT_READY

    @property
    def is_open(self) -> bool:
        """True si el caso espera al profesional o está en contacto directo."""
        return self.status in OPEN_STATUSES

    def is_expired(self, now: datetime) -> bool:
        """True si el caso sigue abierto y ya pasó su vencimiento."""
        return self.is_open and now >= self.expires_at


def open_case(
    case_id: str, thread_id: str, snapshot: CaseSnapshot, now: datetime, window: timedelta
) -> ClinicalCase:
    """Abre un caso pendiente, con aviso de espera para la persona.

    Args:
        case_id: Identificador nuevo.
        thread_id: Hilo del turno sin evidencia.
        snapshot: Resumen clínico.
        now: Fecha y hora (UTC).
        window: Ventana hasta el vencimiento.

    Returns:
        El caso en estado `pendiente`.
    """
    return ClinicalCase(
        case_id, thread_id, snapshot, CaseStatus.PENDING, True, 1, now, now + window
    )


def with_new_gap(case: ClinicalCase, now: datetime, window: timedelta) -> ClinicalCase:
    """Suma un turno sin evidencia al caso abierto y renueva su vencimiento.

    Un mensaje nuevo de la persona reinicia la ventana de WhatsApp (ADR 0023).
    """
    return replace(case, gap_count=case.gap_count + 1, expires_at=now + window)


def renewed(case: ClinicalCase, now: datetime, window: timedelta) -> ClinicalCase:
    """Renueva el vencimiento con un mensaje nuevo de la persona (contacto directo, ADR 0023)."""
    return replace(case, expires_at=now + window)


def apply_action(case: ClinicalCase, action: CaseAction, now: datetime) -> ClinicalCase:
    """Aplica una acción según la tabla de transiciones.

    Args:
        case: Caso actual.
        action: Acción del profesional o vencimiento.
        now: Fecha y hora (UTC).

    Returns:
        El caso en su nuevo estado, con la fecha de cierre si quedó cerrado.

    Raises:
        InvalidCaseTransitionError: Si la acción no aplica al estado actual.
    """
    status = TRANSITIONS.get((case.status, action))
    if status is None:
        raise InvalidCaseTransitionError(f"No se puede {action} un caso {case.status}.")
    closed_at = None if status in OPEN_STATUSES else now
    return replace(case, status=status, closed_at=closed_at)
