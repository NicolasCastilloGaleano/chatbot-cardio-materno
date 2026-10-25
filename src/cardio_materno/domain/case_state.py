"""Estado del caso con la base v2 (MIG-09, ADR 0018).

Con la base v2 (ADR 0017), cada cuadro tiene un registro por etapa. El estado del caso
recuerda, dentro de un hilo, de qué cuadro se está hablando y qué etapas ya se mostraron.
Es la base para elegir la evidencia por etapas (MIG-10 y MIG-11); en este paso solo se
registra.
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
