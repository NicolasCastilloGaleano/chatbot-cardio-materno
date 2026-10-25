"""Base de conocimiento y evidencia recuperada (HU-02, ADR 0008 y ADR 0017).

La base v2 (ADR 0017) organiza los registros por **cuadros** (motivos de consulta): cada
cuadro tiene 12 registros, uno por **etapa** de la conversación, y cada etapa tiene un enfoque
y una ruta fijos (`STAGE_FOCUS`, `STAGE_ROUTE`). Los datos del cuadro (lectura clínica, datos a
extraer, señales de escalamiento y ruta base) viven aparte, en `CaseProfile`, para que nunca
lleguen a la llamada de respuesta.

Los registros de la base v1 (enfoque "Solucionar", sin motivo ni etapa) se siguen aceptando
hasta que se cargue la base v2 (MIG-07).
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.trace import RetrievalStatus

__all__ = [
    "BASE_ROUTES",
    "STAGE_FOCUS",
    "STAGE_ROUTE",
    "CaseProfile",
    "EvidenceItem",
    "Focus",
    "KnowledgeConsistencyError",
    "KnowledgeEntry",
    "RetrievalResult",
    "RetrievalStatus",
    "Route",
    "Stage",
    "missing_stages",
]


class KnowledgeConsistencyError(ValueError):
    """Un registro o un cuadro de la base no cumple las reglas de la base v2."""


class Focus(StrEnum):
    """Enfoque de un registro de la base."""

    INQUIRE = "Indagar"  # Preguntas para entender el caso.
    GUIDE = "Orientar"  # Qué hacer ahora, qué vigilar o qué hacer si ya cedió.
    REFER = "Remitir"  # A dónde ir, cómo trasladarse y qué sigue después de la atención.
    SUPPORT = "Acompañar"  # Verificar el cuadro, acompañar la espera y contener.
    SOLVE = "Solucionar"  # Solo base v1 (orientación general); se retira en MIG-07.


class Stage(StrEnum):
    """Etapa de la conversación a la que responde un registro (base v2)."""

    DISCRIMINATORS = "T1_discriminantes"
    CHARACTERIZATION = "T2_caracterizacion"
    CONTEXT = "T3_contexto"
    IMMEDIATE_ACTION = "accion_inmediata"
    WATCHFUL_WAITING = "vigilancia"
    MILD_COURSE = "evolucion_leve"
    PRIORITY_VISIT = "consulta_prioritaria"
    EMERGENCY_TRANSFER = "traslado_urgencias"
    AFTER_CARE = "seguimiento_tras_atencion"
    CASE_CHECK = "verificacion_del_cuadro"
    WAITING_SUPPORT = "apoyo_en_espera"
    EMOTIONAL_SUPPORT = "apoyo_emocional"


class Route(StrEnum):
    """Ruta a la que apunta un registro o, como ruta base, un cuadro completo."""

    INQUIRY = "indagacion"
    SELF_CARE = "autocuidado"
    FOLLOW_UP = "seguimiento"
    PRIORITY_VISIT = "consulta_prioritaria"
    EMERGENCY = "urgencias"


# Enfoque y ruta fijos de cada etapa (tabla del plan de migración, §2.2).
STAGE_FOCUS: dict[Stage, Focus] = {
    Stage.DISCRIMINATORS: Focus.INQUIRE,
    Stage.CHARACTERIZATION: Focus.INQUIRE,
    Stage.CONTEXT: Focus.INQUIRE,
    Stage.IMMEDIATE_ACTION: Focus.GUIDE,
    Stage.WATCHFUL_WAITING: Focus.GUIDE,
    Stage.MILD_COURSE: Focus.GUIDE,
    Stage.PRIORITY_VISIT: Focus.REFER,
    Stage.EMERGENCY_TRANSFER: Focus.REFER,
    Stage.AFTER_CARE: Focus.REFER,
    Stage.CASE_CHECK: Focus.SUPPORT,
    Stage.WAITING_SUPPORT: Focus.SUPPORT,
    Stage.EMOTIONAL_SUPPORT: Focus.SUPPORT,
}
STAGE_ROUTE: dict[Stage, Route] = {
    Stage.DISCRIMINATORS: Route.INQUIRY,
    Stage.CHARACTERIZATION: Route.INQUIRY,
    Stage.CONTEXT: Route.INQUIRY,
    Stage.IMMEDIATE_ACTION: Route.SELF_CARE,
    Stage.WATCHFUL_WAITING: Route.FOLLOW_UP,
    Stage.MILD_COURSE: Route.SELF_CARE,
    Stage.PRIORITY_VISIT: Route.PRIORITY_VISIT,
    Stage.EMERGENCY_TRANSFER: Route.EMERGENCY,
    Stage.AFTER_CARE: Route.FOLLOW_UP,
    Stage.CASE_CHECK: Route.INQUIRY,
    Stage.WAITING_SUPPORT: Route.FOLLOW_UP,
    Stage.EMOTIONAL_SUPPORT: Route.FOLLOW_UP,
}
# Rutas que puede tener un cuadro completo como ruta base.
BASE_ROUTES = frozenset({Route.SELF_CARE, Route.PRIORITY_VISIT, Route.EMERGENCY})


@dataclass(frozen=True)
class KnowledgeEntry:
    """Registro pregunta/respuesta de la base de conocimiento.

    Attributes:
        id: Identificador estable (base v1: hash del piloto; v2: dominio, motivo y etapa).
        domain: Dominio de salud.
        category: Categoría temática.
        focus: Enfoque del registro.
        question: Pregunta tipo (en la base v2, un mensaje real de una persona).
        answer: Respuesta validada para el prototipo.
        motive: Motivo de consulta (cuadro) al que pertenece; vacío en la base v1.
        stage: Etapa de la conversación; None en la base v1.
        route: Ruta del registro; None en la base v1.
        source: Fuente clínica del registro (B-019); vacía si aún no se registró.
        validated_by: Quién validó el registro (B-019); vacío si aún no se validó.
        validated_at: Fecha de validación (B-019); vacía si aún no se validó.

    Raises:
        KnowledgeConsistencyError: Si el enfoque o la ruta no corresponden a la etapa, o si
            un registro v2 no tiene motivo.
    """

    id: str
    domain: Domain
    category: str
    focus: Focus
    question: str
    answer: str
    motive: str = ""
    stage: Stage | None = None
    route: Route | None = None
    source: str = ""
    validated_by: str = ""
    validated_at: str = ""

    def __post_init__(self) -> None:
        """Verifica que el registro sea un registro v1 o un registro v2 coherente."""
        if self.stage is None:
            check_v1_entry(self)
        else:
            check_v2_entry(self, self.stage)

    @property
    def embedding_text(self) -> str:
        """Texto con el que se calcula su embedding (mismo formato que el piloto)."""
        return f"Pregunta: {self.question} \nRespuesta: {self.answer}"


def check_v1_entry(entry: KnowledgeEntry) -> None:
    """Un registro sin etapa no puede tener ruta, motivo ni un enfoque solo de la base v2.

    Raises:
        KnowledgeConsistencyError: Si mezcla campos de la base v1 y la v2.
    """
    if entry.route is not None or entry.motive:
        raise KnowledgeConsistencyError(f"{entry.id}: tiene ruta o motivo pero no etapa")
    if entry.focus not in (Focus.INQUIRE, Focus.SOLVE):
        raise KnowledgeConsistencyError(f"{entry.id}: el enfoque '{entry.focus}' exige una etapa")


def check_v2_entry(entry: KnowledgeEntry, stage: Stage) -> None:
    """Un registro con etapa debe tener motivo y el enfoque y la ruta de su etapa.

    Raises:
        KnowledgeConsistencyError: Si falta el motivo o no coinciden el enfoque o la ruta.
    """
    if not entry.motive.strip():
        raise KnowledgeConsistencyError(f"{entry.id}: un registro con etapa necesita motivo")
    if entry.focus is not STAGE_FOCUS[stage] or entry.route is not STAGE_ROUTE[stage]:
        raise KnowledgeConsistencyError(
            f"{entry.id}: la etapa '{stage}' exige enfoque '{STAGE_FOCUS[stage]}' y ruta "
            f"'{STAGE_ROUTE[stage]}' (tiene '{entry.focus}' y '{entry.route}')"
        )


@dataclass(frozen=True)
class CaseProfile:
    """Datos de un cuadro (motivo de consulta) de la base v2, comunes a sus 12 registros.

    La lectura clínica es lenguaje técnico para auditar: **nunca** se muestra a la persona ni
    se envía a la llamada de respuesta (el servicio no diagnostica).

    Attributes:
        motive: Motivo de consulta (identificador del cuadro).
        domain: Dominio de salud.
        category: Categoría temática.
        clinical_reading: Interpretación clínica del cuadro (solo auditoría).
        data_to_collect: Datos que conviene obtener al indagar.
        escalation_signs: Señales que obligan a escalar, en lenguaje de la persona.
        base_route: Ruta base del cuadro (autocuidado, consulta prioritaria o urgencias).

    Raises:
        KnowledgeConsistencyError: Si la ruta base no es una de `BASE_ROUTES`.
    """

    motive: str
    domain: Domain
    category: str
    clinical_reading: str
    data_to_collect: tuple[str, ...]
    escalation_signs: tuple[str, ...]
    base_route: Route

    def __post_init__(self) -> None:
        """Verifica la ruta base del cuadro."""
        if self.base_route not in BASE_ROUTES:
            raise KnowledgeConsistencyError(
                f"{self.motive}: la ruta base '{self.base_route}' no es válida para un cuadro"
            )


def missing_stages(entries: Iterable[KnowledgeEntry]) -> dict[str, tuple[Stage, ...]]:
    """Etapas que le faltan a cada cuadro de la base v2 (los registros v1 se ignoran).

    Args:
        entries: Registros de la base.

    Returns:
        Motivo → etapas que no tienen registro, solo para los cuadros incompletos.
    """
    present: defaultdict[str, set[Stage]] = defaultdict(set)
    for entry in entries:
        if entry.stage is not None:
            present[entry.motive].add(entry.stage)
    return {
        motive: tuple(stage for stage in Stage if stage not in stages)
        for motive, stages in present.items()
        if len(stages) < len(Stage)
    }


@dataclass(frozen=True)
class EvidenceItem:
    """Registro recuperado como evidencia para un turno.

    Attributes:
        label: Etiqueta corta que ve el agente (E1, E2…).
        entry: Registro de la base.
        score: Similitud coseno con la consulta (no es confianza clínica).
    """

    label: str
    entry: KnowledgeEntry
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    """Evidencia encontrada para una consulta.

    Attributes:
        status: Si hay evidencia suficiente, insuficiente o el buscador no está disponible.
        items: Evidencia que superó el umbral (vacío si no hay).
        best_score: Mejor similitud vista, aunque no supere el umbral (para diagnóstico).
    """

    status: RetrievalStatus
    items: tuple[EvidenceItem, ...] = ()
    best_score: float = 0.0

    @property
    def labels(self) -> tuple[str, ...]:
        """Etiquetas de la evidencia ofrecida."""
        return tuple(item.label for item in self.items)
