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
    ANSWER_AND_INQUIRE = "responder_e_indagar"
    ABSTAIN = "abstenerse"
    CLOSE = "cerrar"


class SelectionVerdict(StrEnum):
    """Si la evidencia atiende la consulta, según el selector (HU-13, ADR 0019)."""

    ANSWERS = "responde"
    PARTIAL = "parcial"
    NO_ANSWER = "no_responde"


class RecordFit(StrEnum):
    """Si un registro corresponde a la situación de la persona, según el selector."""

    YES = "si"
    PARTLY = "en_parte"
    NO = "no"


@dataclass(frozen=True)
class RecordReview:
    """Evaluación de un registro frente al caso, antes de elegir sus frases (HU-13).

    Attributes:
        label: Etiqueta del registro (E1, E2…).
        fit: Si corresponde a la situación de la persona.
        unsaid: Datos que el registro supone y la persona no dio ("" si no hay).
    """

    label: str
    fit: RecordFit
    unsaid: str = ""


@dataclass(frozen=True)
class OfferedSentence:
    """Frase de un registro ofrecida al selector de evidencia (HU-13).

    Attributes:
        id: Identificador de la frase (`E2.3`: tercera frase del registro E2).
        text: Texto de la frase, tal como está en el registro.
    """

    id: str
    text: str


@dataclass(frozen=True)
class SelectionTrace:
    """Lo que hizo el selector de evidencia en un turno (HU-13, ADR 0019).

    Attributes:
        offered: Frases ofrecidas.
        verdict: Veredicto del selector (None si la llamada falló).
        selected: Ids que eligió, en orden de importancia.
        context: Ids agregados porque una frase elegida depende de ellos.
        added_notices: Avisos de atención de los registros elegidos que el selector no eligió.
        omitted_notices: Avisos de atención de los registros que no eligió.
        applied: True si el resultado decidió la respuesta; False si solo se observó.
        reviews: Evaluación de cada registro frente al caso.
        failure: Causa, si la llamada falló.
        shown: Frases que la regla deja mostrar (con `applied`, las que se usaron).
    """

    offered: tuple[OfferedSentence, ...]
    verdict: SelectionVerdict | None = None
    selected: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    added_notices: tuple[str, ...] = ()
    omitted_notices: tuple[str, ...] = ()
    applied: bool = False
    reviews: tuple[RecordReview, ...] = ()
    failure: str = ""
    shown: tuple[str, ...] = ()


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
        informational: Si el turno era informativo: no había una situación que caracterizar.
        has_answer: Si la evidencia incluía un registro que orienta (*Solucionar*).
        rule_mode: Modo que eligió la regla, si el selector de evidencia lo cambió (HU-13).
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
    informational: bool = False
    has_answer: bool = True
    rule_mode: TurnMode | None = None


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
class ModelUsage:
    """Cómo se repartió el tiempo de una llamada al modelo (lo informa Ollama).

    Sirve para saber si la lentitud viene de leer el prompt o de generar la respuesta.

    Attributes:
        stage: Etapa del turno (análisis o respuesta); "" mientras no se asigna.
        prompt_tokens: Tokens del prompt que el modelo procesó (sin los que ya tenía en caché).
        prompt_seconds: Segundos que tardó en procesarlos.
        output_tokens: Tokens que generó.
        output_seconds: Segundos que tardó en generarlos.
    """

    stage: str
    prompt_tokens: int
    prompt_seconds: float
    output_tokens: int
    output_seconds: float


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
        model_usage: Lectura del prompt y generación de cada llamada al modelo, por etapa.
        urgent_accompaniment: True si el turno acompañó una urgencia inmediata ya avisada:
            sin indagar y sin preguntas (B-030).
        selection: Lo que hizo el selector de evidencia (HU-13); None si no corrió.
        urgent_follow_up: True si es la orientación automática que sigue al aviso de una
            urgencia (B-034, ADR 0021).
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
    model_usage: tuple[ModelUsage, ...] = ()
    urgent_accompaniment: bool = False
    selection: SelectionTrace | None = None
    urgent_follow_up: bool = False

    @property
    def uncited(self) -> bool:
        """True si había evidencia suficiente y el agente no citó ninguna (para auditar)."""
        return self.retrieval_status is RetrievalStatus.SUFFICIENT and not self.cited_evidence
