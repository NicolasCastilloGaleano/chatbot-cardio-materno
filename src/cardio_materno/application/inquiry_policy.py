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
from dataclasses import dataclass, replace
from enum import StrEnum

from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import EvidenceItem, Focus
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
        has_answer: Si la evidencia incluye un registro que orienta (enfoque *Solucionar*).
    """

    best_score: float
    margin: float
    agreement: int
    top_category: str
    has_answer: bool = True


@dataclass(frozen=True)
class TurnIntent:
    """Qué busca la persona con el mensaje, según el análisis.

    Attributes:
        wants_guidance: Pide directamente qué hacer.
        informational: Hace una pregunta de información o no reporta síntomas: no hay una
            situación que caracterizar.
    """

    wants_guidance: bool = False
    informational: bool = False

    @property
    def direct(self) -> bool:
        """True si al turno no le corresponde indagar."""
        return self.wants_guidance or self.informational


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


def search_signals(
    candidates: Sequence[EvidenceItem],
    best_score: float,
    evidence: Sequence[EvidenceItem] = (),
) -> InquirySignals:
    """Calcula las señales con los candidatos ordenados de mayor a menor similitud.

    Args:
        candidates: Candidatos sobre el piso de indagación.
        best_score: Mejor similitud vista en la búsqueda (aunque no haya candidatos).
        evidence: Evidencia encontrada (sobre el umbral del RAG).

    Returns:
        Las señales de la regla.
    """
    has_answer = any(item.entry.focus is Focus.SOLVE for item in evidence)
    if not candidates:
        return InquirySignals(best_score, best_score, 0, "", has_answer)
    first = candidates[0]
    second = candidates[1].score if len(candidates) > 1 else 0.0
    category = first.entry.category
    agreement = sum(1 for item in candidates if item.entry.category == category)
    margin = round(first.score - second, 4)
    return InquirySignals(first.score, margin, agreement, category, has_answer)


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
    intent: TurnIntent,
    policy: InquiryPolicy,
    applied: bool,
) -> InquiryTrace:
    """Aplica la regla del ADR 0017 y arma lo que se registra en la traza.

    Args:
        signals: Señales de la búsqueda del turno.
        state: Estado de la indagación según la última respuesta del hilo.
        intent: Qué busca la persona con el mensaje.
        policy: Umbrales de la regla.
        applied: True si la regla decide el turno (`activo`); False si solo se observa.

    Returns:
        El modo elegido, el turno de indagación, las señales y si hubo avance.
    """
    progress = made_progress(signals, state, policy) if state.inquiring else None
    stalled = state.stalled + 1 if progress is False else 0
    mode = choose_mode(signals, state, stalled, intent, policy)
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
        wants_guidance=intent.wants_guidance,
        applied=applied,
        informational=intent.informational,
        has_answer=signals.has_answer,
    )


def choose_mode(
    signals: InquirySignals,
    state: InquiryState,
    stalled: int,
    intent: TurnIntent,
    policy: InquiryPolicy,
) -> TurnMode:
    """Modo del turno, en el orden de la tabla del ADR 0017 y sus ajustes del 2026-10-31."""
    if is_clear_evidence(signals, policy):
        return TurnMode.ANSWER
    exhausted = state.inquiring and is_exhausted(state, stalled, policy)
    if intent.direct or exhausted:
        return (
            TurnMode.ANSWER if is_answerable(signals, policy) else no_answer_mode(state, exhausted)
        )
    if signals.best_score >= policy.inquiry_floor:
        return TurnMode.INQUIRE
    return no_answer_mode(state, exhausted)


def mode_without_answer(
    inquiry: InquiryTrace, state: InquiryState, policy: InquiryPolicy
) -> InquiryTrace:
    """Decisión final si la regla dijo responder y el selector no deja nada visible (HU-13).

    Args:
        inquiry: Decisión de la regla.
        state: Estado de la indagación según la última respuesta del hilo.
        policy: Umbrales de la regla.

    Returns:
        La decisión con el modo final y el de la regla: indagar si la persona reporta síntomas,
        no hizo un pedido directo y quedan turnos; si no, abstenerse o cerrar.
    """
    exhausted = state.inquiring and is_exhausted(state, inquiry.stalled, policy)
    decided = replace(inquiry, rule_mode=inquiry.mode)
    if inquiry.wants_guidance or inquiry.informational or exhausted:
        return replace(decided, mode=no_answer_mode(state, exhausted))
    previous_turns = state.turn if state.inquiring else 0
    return replace(decided, mode=TurnMode.INQUIRE, turn=previous_turns + 1)


def is_clear_evidence(signals: InquirySignals, policy: InquiryPolicy) -> bool:
    """True si el mejor registro supera el umbral para responder y se distingue o coincide."""
    distinct = signals.margin >= policy.min_margin or signals.agreement >= policy.min_agreement
    return signals.has_answer and signals.best_score >= policy.answer_threshold and distinct


def is_answerable(signals: InquirySignals, policy: InquiryPolicy) -> bool:
    """True si hay evidencia suficiente con un registro que orienta."""
    return signals.has_answer and signals.best_score >= policy.min_similarity


def is_exhausted(state: InquiryState, stalled: int, policy: InquiryPolicy) -> bool:
    """True si se alcanzó el máximo de turnos de indagación o no hubo avance."""
    return state.turn >= policy.max_turns or stalled >= policy.max_stalled


def no_answer_mode(state: InquiryState, exhausted: bool) -> TurnMode:
    """Sin respuesta posible: abstención que pide detalles o, si ya se preguntó, cierre."""
    asked = exhausted or state.last_mode in (TurnMode.INQUIRE, TurnMode.ABSTAIN)
    return TurnMode.CLOSE if asked else TurnMode.ABSTAIN
