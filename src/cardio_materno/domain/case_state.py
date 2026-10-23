"""Estado del caso y reglas de etapas de la base v2 (MIG-09, MIG-11 y MIG-13, ADR 0017).

Con la base v2 (ADR 0016), cada cuadro tiene un registro por etapa. Estas reglas deciden,
sin el LLM, de qué etapas puede salir la evidencia del turno:

1. **Indagación primero:** mientras falten etapas de `INQUIRY_SEQUENCE` (T1 → T2 → T3 →
   verificación del cuadro), solo se ofrece la siguiente, o una etapa de intención explícita
   (`INTENT_STAGES`: qué hago ya, ya me atendieron, estoy esperando, tengo miedo). Así, el
   primer turno no puede terminar en una remisión, salvo que el registro T1 del cuadro lo diga.
2. **Transición por la ruta base:** justo después de verificar el cuadro, se muestra la etapa
   que corresponde a su ruta base (`ROUTE_DEFAULT_STAGE`).
3. **Después:** cualquier etapa que no sea de indagación, según lo que pregunte la persona.

Las alarmas deterministas (ADR 0007) se evalúan antes y siempre tienen prioridad: estas
reglas nunca rebajan una alarma.
"""

from dataclasses import dataclass

from cardio_materno.domain.knowledge import Route, Stage

INQUIRY_SEQUENCE = (
    Stage.DISCRIMINATORS,
    Stage.CHARACTERIZATION,
    Stage.CONTEXT,
    Stage.CASE_CHECK,
)
# Etapas a las que la persona puede saltar en cualquier momento con lo que escribe.
INTENT_STAGES = (
    Stage.IMMEDIATE_ACTION,
    Stage.AFTER_CARE,
    Stage.WAITING_SUPPORT,
    Stage.EMOTIONAL_SUPPORT,
)
AFTER_INQUIRY_STAGES = tuple(stage for stage in Stage if stage not in INQUIRY_SEQUENCE)
# Etapa con la que se cierra la indagación según la ruta base del cuadro.
ROUTE_DEFAULT_STAGE = {
    Route.SELF_CARE: Stage.IMMEDIATE_ACTION,
    Route.PRIORITY_VISIT: Stage.PRIORITY_VISIT,
    Route.EMERGENCY: Stage.EMERGENCY_TRANSFER,
}


@dataclass(frozen=True)
class CaseState:
    """Estado del caso dentro de un hilo: el cuadro y las etapas ya mostradas.

    Attributes:
        motive: Motivo de consulta (cuadro) identificado.
        stage: Etapa del último registro mostrado.
        visited: Etapas mostradas de este cuadro, en orden y sin repetir.
    """

    motive: str
    stage: Stage
    visited: tuple[Stage, ...]


@dataclass(frozen=True)
class StagePlan:
    """De qué etapas puede salir la evidencia del turno.

    Attributes:
        stages: Etapas permitidas (la similitud elige entre ellas).
        fixed: True si la etapa está decidida (una sola, sin comparar similitud).
    """

    stages: tuple[Stage, ...]
    fixed: bool = False


def next_inquiry_stage(case: CaseState | None) -> Stage | None:
    """Siguiente etapa de indagación que no se ha mostrado (None si ya se mostraron todas)."""
    visited = case.visited if case is not None else ()
    return next((stage for stage in INQUIRY_SEQUENCE if stage not in visited), None)


def plan_stages(case: CaseState | None, base_route: Route) -> StagePlan:
    """Etapas permitidas para el próximo registro del cuadro.

    Args:
        case: Estado del caso (None si el cuadro se acaba de identificar).
        base_route: Ruta base del cuadro.

    Returns:
        La siguiente de indagación con las de intención; la de la ruta base, fija, justo
        después de verificar el cuadro; o todas las que no son de indagación.
    """
    following = next_inquiry_stage(case)
    if following is not None:
        return StagePlan((following, *INTENT_STAGES))
    if case is not None and case.stage is Stage.CASE_CHECK:
        return StagePlan((ROUTE_DEFAULT_STAGE[base_route],), fixed=True)
    return StagePlan(AFTER_INQUIRY_STAGES)


def advance(case: CaseState | None, motive: str, stage: Stage) -> CaseState:
    """Estado después de mostrar un registro del cuadro.

    Si el motivo cambia, el caso empieza de nuevo con ese registro.
    """
    if case is None or case.motive != motive:
        return CaseState(motive, stage, (stage,))
    visited = case.visited if stage in case.visited else (*case.visited, stage)
    return CaseState(motive, stage, visited)
