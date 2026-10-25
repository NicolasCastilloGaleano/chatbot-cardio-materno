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
    """

    supported: int
    total: int
    literal: bool = False
    dropped: tuple[str, ...] = ()


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
        case_motive: Cuadro de la base v2 del registro principal ("" si no aplica).
        case_stage: Etapa de ese registro ("" si no aplica).
        case_visited: Etapas del cuadro ya mostradas en el hilo, en orden (estado del caso,
            ADR 0018).
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
    case_motive: str = ""
    case_stage: str = ""
    case_visited: tuple[str, ...] = ()

    @property
    def uncited(self) -> bool:
        """True si había evidencia suficiente y el agente no citó ninguna (para auditar)."""
        return self.retrieval_status is RetrievalStatus.SUFFICIENT and not self.cited_evidence
