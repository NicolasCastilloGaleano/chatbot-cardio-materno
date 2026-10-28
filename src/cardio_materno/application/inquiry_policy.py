"""Regla determinista de la indagación guiada por la evidencia (HU-11, ADR 0017).

En cada turno sin alarma nueva, la regla decide con las señales de la búsqueda si se
responde con evidencia, se indaga con preguntas, se pide más detalle (abstención) o se
cierra con un mensaje honesto. El LLM no interviene: solo aporta `wants_guidance` desde el
análisis. El estado de la indagación viaja en la traza de la última respuesta del hilo, así
que no hace falta almacenamiento nuevo.

Modos de activación (`INQUIRY_MODE`): `apagado` no calcula nada; `observar` calcula el modo y
lo registra en la traza, pero el turno se resuelve como antes; `activo` deja decidir a la
regla.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import EvidenceItem
from cardio_materno.domain.trace import InquiryTrace, TurnMode


class InquiryActivation(StrEnum):
    """Cómo participa la regla de indagación en el turno (`INQUIRY_MODE`)."""

    OFF = "apagado"
    OBSERVE = "observar"
    ACTIVE = "activo"


@dataclass(frozen=True)
class InquiryPolicy:
    """Umbrales de la regla (propuestas del ADR 0017, se calibran en modo observar).

    Attributes:
        min_similarity: Umbral de evidencia actual: con él se puede responder.
        inquiry_floor: Similitud mínima para indagar.
        answer_threshold: Similitud con la que la evidencia es clara para responder.
        min_margin: Ventaja mínima del primer candidato sobre el segundo.
        min_agreement: Candidatos (incluido el primero) con la categoría del primero.
        progress_delta: Subida mínima del mejor puntaje que cuenta como avance.
        max_turns: Máximo de turnos de indagación seguidos.
        max_stalled: Turnos de indagación seguidos sin avance que detienen la indagación.
    """

    min_similarity: float = 0.50
    inquiry_floor: float = 0.40
    answer_threshold: float = 0.68
    min_margin: float = 0.03
    min_agreement: int = 2
    progress_delta: float = 0.02
    max_turns: int = 3
    max_stalled: int = 2


@dataclass(frozen=True)
class InquirySignals:
    """Señales de la búsqueda del turno.

    Attributes:
        best_score: Mejor similitud vista (`s1`).
        margin: Diferencia entre el primer y el segundo candidato.
        agreement: Candidatos (incluido el primero) con la categoría del primero.
        top_category: Categoría del primer candidato ("" si no hay candidatos).
    """

    best_score: float
    margin: float
    agreement: int
    top_category: str


@dataclass(frozen=True)
class InquiryState:
    """Estado de la indagación según la última respuesta del hilo.

    Attributes:
        last_mode: Modo de la última respuesta (None si no hay o es de otro tipo).
        turn: Turnos de indagación seguidos hasta la última respuesta.
        stalled: Turnos de indagación seguidos sin avance.
        best_score: Mejor similitud de la última respuesta.
        top_category: Categoría del primer candidato de la última respuesta.
    """

    last_mode: TurnMode | None = None
    turn: int = 0
    stalled: int = 0
    best_score: float = 0.0
    top_category: str = ""

    @property
    def inquiring(self) -> bool:
        """True si la última respuesta fue un turno de indagación."""
        return self.last_mode is TurnMode.INQUIRE


def search_signals(candidates: Sequence[EvidenceItem], best_score: float) -> InquirySignals:
    """Calcula las señales con los candidatos ordenados de mayor a menor similitud.

    Args:
        candidates: Candidatos sobre el piso de indagación.
        best_score: Mejor similitud vista en la búsqueda (aunque no haya candidatos).

    Returns:
        Las señales de la regla.
    """
    if not candidates:
        return InquirySignals(best_score, best_score, 0, "")
    first = candidates[0]
    second = candidates[1].score if len(candidates) > 1 else 0.0
    category = first.entry.category
    agreement = sum(1 for item in candidates if item.entry.category == category)
    return InquirySignals(first.score, round(first.score - second, 4), agreement, category)


def previous_state(recent: Sequence[ChatMessage]) -> InquiryState:
    """Estado de la indagación según la última respuesta del asistente en el hilo.

    Args:
        recent: Mensajes recientes del hilo que continúa (vacío si el tema es nuevo).

    Returns:
        El estado guardado en la traza, o un estado vacío.
    """
    replies = [m for m in recent if m.role is Role.ASSISTANT]
    trace = replies[-1].trace if replies else None
    inquiry = trace.inquiry if trace is not None else None
    if inquiry is None:
        return InquiryState()
    return InquiryState(
        inquiry.mode, inquiry.turn, inquiry.stalled, inquiry.best_score, inquiry.top_category
    )


def made_progress(signals: InquirySignals, state: InquiryState, policy: InquiryPolicy) -> bool:
    """True si el mejor puntaje subió lo suficiente o se mantuvo la categoría del primero."""
    rose = signals.best_score >= state.best_score + policy.progress_delta
    same_category = bool(signals.top_category) and signals.top_category == state.top_category
    return rose or same_category


def evaluate_inquiry(
    signals: InquirySignals,
    state: InquiryState,
    wants_guidance: bool,
    policy: InquiryPolicy,
    applied: bool,
) -> InquiryTrace:
    """Aplica la regla del ADR 0017 y arma lo que se registra en la traza.

    Args:
        signals: Señales de la búsqueda del turno.
        state: Estado de la indagación según la última respuesta del hilo.
        wants_guidance: Si la persona pidió directamente qué hacer (análisis v7).
        policy: Umbrales de la regla.
        applied: True si la regla decide el turno (`activo`); False si solo se observa.

    Returns:
        El modo elegido, el turno de indagación, las señales y si hubo avance.
    """
    progress = made_progress(signals, state, policy) if state.inquiring else None
    stalled = state.stalled + 1 if progress is False else 0
    mode = choose_mode(signals, state, stalled, wants_guidance, policy)
    previous_turns = state.turn if state.inquiring else 0
    turn = previous_turns + 1 if mode is TurnMode.INQUIRE else previous_turns
    return InquiryTrace(
        mode=mode,
        turn=turn,
        stalled=stalled,
        best_score=signals.best_score,
        margin=signals.margin,
        agreement=signals.agreement,
        top_category=signals.top_category,
        progress=progress,
        wants_guidance=wants_guidance,
        applied=applied,
    )


def choose_mode(
    signals: InquirySignals,
    state: InquiryState,
    stalled: int,
    wants_guidance: bool,
    policy: InquiryPolicy,
) -> TurnMode:
    """Modo del turno, en el orden de la tabla del ADR 0017."""
    if is_clear_evidence(signals, policy):
        return TurnMode.ANSWER
    forced = forced_end(signals, state, stalled, wants_guidance, policy)
    if forced is not None:
        return forced
    if signals.best_score >= policy.inquiry_floor:
        return TurnMode.INQUIRE
    asked = state.last_mode in (TurnMode.INQUIRE, TurnMode.ABSTAIN)
    return TurnMode.CLOSE if asked else TurnMode.ABSTAIN


def is_clear_evidence(signals: InquirySignals, policy: InquiryPolicy) -> bool:
    """True si el mejor registro supera el umbral para responder y se distingue o coincide."""
    distinct = signals.margin >= policy.min_margin or signals.agreement >= policy.min_agreement
    return signals.best_score >= policy.answer_threshold and distinct


def forced_end(
    signals: InquirySignals,
    state: InquiryState,
    stalled: int,
    wants_guidance: bool,
    policy: InquiryPolicy,
) -> TurnMode | None:
    """Fin obligado de la indagación: pedido directo, máximo de turnos o falta de avance.

    Returns:
        Responder si hay evidencia suficiente, cerrar si no, o None si no hay fin obligado.
    """
    exhausted = state.turn >= policy.max_turns or stalled >= policy.max_stalled
    if not (wants_guidance or (state.inquiring and exhausted)):
        return None
    if signals.best_score >= policy.min_similarity:
        return TurnMode.ANSWER
    return TurnMode.CLOSE if state.inquiring else None
