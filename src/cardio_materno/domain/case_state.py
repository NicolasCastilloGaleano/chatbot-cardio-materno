"""Estado del caso con la base v2 (MIG-09, ADR 0018).

Con la base v2 (ADR 0017), cada cuadro tiene un registro por etapa. El estado del caso
recuerda, dentro de un hilo, de qué cuadro se está hablando y qué etapas ya se mostraron.
Con él, dentro del cuadro identificado no se repite una etapa ya mostrada
(`pending_stages`, MIG-10). El orden de las etapas llega en MIG-11.
"""

from dataclasses import dataclass

from cardio_materno.domain.knowledge import Stage


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


def advance(case: CaseState | None, motive: str, stage: Stage) -> CaseState:
    """Estado después de mostrar un registro del cuadro.

    Args:
        case: Estado anterior (None si el hilo aún no tiene cuadro).
        motive: Cuadro del registro mostrado.
        stage: Etapa del registro mostrado.

    Returns:
        El estado con la etapa agregada; si el cuadro cambia, el caso empieza de nuevo.
    """
    if case is None or case.motive != motive:
        return CaseState(motive, stage, (stage,))
    visited = case.visited if stage in case.visited else (*case.visited, stage)
    return CaseState(motive, stage, visited)


def pending_stages(case: CaseState | None) -> tuple[Stage, ...]:
    """Etapas del cuadro que aún no se mostraron (todas si ya se mostraron todas).

    Args:
        case: Estado del caso (None si el cuadro se acaba de identificar).

    Returns:
        Las etapas sin mostrar, en el orden de `Stage`.
    """
    visited = case.visited if case is not None else ()
    pending = tuple(stage for stage in Stage if stage not in visited)
    return pending or tuple(Stage)
