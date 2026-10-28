"""Traza de cómo se produjo una respuesta del asistente (auditoría, HU-03 y HU-02).

Se guarda junto a cada respuesta del asistente para poder explicar después qué síntomas
identificó el agente, qué evidencia se le ofreció, cuál citó y cuánto tardó cada etapa.
"""

from dataclasses import dataclass
from enum import StrEnum


class RetrievalStatus(StrEnum):
    """Resultado de buscar evidencia."""

    SUFFICIENT = "suficiente"
    INSUFFICIENT = "insuficiente"
    UNAVAILABLE = "no_disponible"


class TurnMode(StrEnum):
    """Modo de un turno sin alarma nueva según la regla de indagación (HU-11, ADR 0017)."""

    ANSWER = "responder"
    INQUIRE = "indagar"
    ABSTAIN = "abstenerse"
    CLOSE = "cerrar"


@dataclass(frozen=True)
class InquiryTrace:
    """Decisión de la regla de indagación en un turno (HU-11, ADR 0017).

    También es el estado que lee el turno siguiente del mismo hilo.

    Attributes:
        mode: Modo elegido por la regla.
        turn: Turnos de indagación seguidos, incluido este si es de indagación.
        stalled: Turnos de indagación seguidos sin avance.
        best_score: Mejor similitud de la búsqueda (`s1`).
        margin: Ventaja del primer candidato sobre el segundo.
        agreement: Candidatos (incluido el primero) con la categoría del primero.
        top_category: Categoría del primer candidato ("" si no hay).
        progress: Si hubo avance frente al turno de indagación anterior (None si no lo hubo).
        wants_guidance: Si la persona pidió directamente qué hacer.
        applied: True si la regla decidió el turno; False si solo se observó.
    """

    mode: TurnMode
    turn: int = 0
    stalled: int = 0
    best_score: float = 0.0
    margin: float = 0.0
    agreement: int = 0
    top_category: str = ""
    progress: bool | None = None
    wants_guidance: bool = False
    applied: bool = False


@dataclass(frozen=True)
class EvidenceRef:
    """Referencia a un registro de evidencia ofrecido al agente.

    Attributes:
        label: Etiqueta que vio el agente (E1, E2…).
        entry_id: Identificador del registro en la base.
        score: Similitud coseno con la consulta.
        category: Categoría del registro.
    """

    label: str
    entry_id: str
    score: float
    category: str


@dataclass(frozen=True)
class StageTiming:
    """Duración de una etapa del turno.

    Attributes:
        stage: Nombre de la etapa (análisis, RAG, respuesta).
        seconds: Duración en segundos.
    """

    stage: str
    seconds: float


@dataclass(frozen=True)
class GroundingCheck:
    """Resultado de verificar el respaldo de una respuesta en la evidencia (ADR 0010).

    Attributes:
        supported: Frases que se mostraron (respaldadas o permitidas sin cita).
        total: Frases que redactó el agente.
        literal: True si se mostró el texto literal del registro en lugar de la redacción.
        dropped: Frases descartadas (para auditar).
        literal_shown: Con texto literal, frases del registro que se mostraron (B-028).
        literal_total: Con texto literal, frases que tiene el registro.
    """

    supported: int
    total: int
    literal: bool = False
    dropped: tuple[str, ...] = ()
    literal_shown: int = 0
    literal_total: int = 0


@dataclass(frozen=True)
class ReplyTrace:
    """Lo que se registra de una respuesta del asistente cuando se consultó al agente.

    Attributes:
        reported_symptoms: Síntomas que identificó la llamada de análisis (filtro 2).
        evidence: Evidencia ofrecida a la llamada de respuesta.
        cited_evidence: Etiquetas que el agente dijo usar.
        retrieval_status: Resultado de la búsqueda (None si no se buscó evidencia).
        best_score: Mejor similitud vista en la búsqueda (None si no se buscó).
        timings: Duración de cada etapa.
        scope: Alcance aplicado al mensaje (en_alcance, conversacional, fuera_de_alcance).
        scope_reason: Motivo corto de la decisión de alcance.
        grounding: Verificación del respaldo (None si no hubo redacción con evidencia).
        unstated_symptoms: Síntomas con datos (números) que la persona no escribió (auditoría).
        search_query: Consulta con la que se buscó la evidencia ("" si no se buscó).
        reported_signs: Códigos de signos que marcó el análisis (ADR 0012).
        domain_fallback: True si, sin evidencia en el dominio del análisis, la búsqueda se
            amplió a los dos dominios (HU-02, 2026-10-26).
        reminded_rules: Reglas ya avisadas en el hilo que solo se recordaron (ADR 0018).
        inquiry: Decisión de la regla de indagación (HU-11); None si no se evaluó.
        about_health: Si el análisis dijo que el mensaje nuevo, por sí mismo, trata de salud
            (prompt v7, ADR 0009). True en trazas anteriores.
    """

    reported_symptoms: tuple[str, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()
    cited_evidence: tuple[str, ...] = ()
    retrieval_status: RetrievalStatus | None = None
    best_score: float | None = None
    timings: tuple[StageTiming, ...] = ()
    scope: str | None = None
    scope_reason: str = ""
    grounding: GroundingCheck | None = None
    unstated_symptoms: tuple[str, ...] = ()
    search_query: str = ""
    reported_signs: tuple[str, ...] = ()
    domain_fallback: bool = False
    reminded_rules: tuple[str, ...] = ()
    inquiry: InquiryTrace | None = None
    about_health: bool = True

    @property
    def uncited(self) -> bool:
        """True si había evidencia suficiente y el agente no citó ninguna (para auditar)."""
        return self.retrieval_status is RetrievalStatus.SUFFICIENT and not self.cited_evidence
