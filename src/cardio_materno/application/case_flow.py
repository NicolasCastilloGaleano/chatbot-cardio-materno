"""Recuperación dirigida por el estado del caso con la base v2 (MIG-09 a MIG-11, ADR 0018).

Cada turno con evidencia hace, a lo sumo, dos búsquedas con el mismo texto (un solo embedding):

1. **Identificar el cuadro** (si el hilo aún no tiene uno o la persona cambió de tema): se
   busca en toda la base, **en los dos dominios** (un error de dominio en el análisis ya no
   confina la búsqueda), con el umbral de la política. El cuadro es el del mejor registro.
2. **Elegir la etapa:** dentro del cuadro, entre las etapas que permiten las reglas
   deterministas (`domain/case_state.py::plan_stages`): indagar primero, luego la ruta base
   del cuadro, sin repetir lo ya mostrado. Aquí no se exige el umbral: con el cuadro
   identificado, una respuesta corta ("sí, desde ayer") también recibe su registro.

El estado del caso no tiene almacenamiento propio: viaja en la traza de cada respuesta del
asistente y se recupera de los mensajes recientes del hilo. Mientras el análisis diga
"continuar", el cuadro se mantiene.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery, KnowledgeRetriever
from cardio_materno.domain.case_state import CaseState, advance, plan_stages
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import CaseProfile, RetrievalResult, RetrievalStatus, Stage


@dataclass(frozen=True)
class CaseRetrieval:
    """Evidencia del turno y estado del caso después de mostrarla.

    Attributes:
        result: Evidencia (registros del cuadro, o el resultado sin evidencia).
        case: Estado del caso tras este turno (None si no se identificó un cuadro).
    """

    result: RetrievalResult
    case: CaseState | None


class CaseFlow:
    """Identifica el cuadro, lo mantiene en el hilo y elige su registro del turno."""

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        profiles: Mapping[str, CaseProfile],
        evidence_items: int,
    ) -> None:
        """Crea el flujo.

        Args:
            retriever: Buscador de evidencia sobre la base v2.
            profiles: Cuadros por motivo.
            evidence_items: Registros que se entregan al agente (`case_top_k`).
        """
        self._retriever = retriever
        self._profiles = profiles
        self._evidence_items = evidence_items

    def retrieve(
        self, query: EvidenceQuery, analysis: AnalysisTurn, recent: Sequence[ChatMessage]
    ) -> CaseRetrieval:
        """Evidencia del turno según el estado del caso.

        Args:
            query: Consulta armada con el análisis (su filtro de dominio se ignora).
            analysis: Análisis del turno (decide si sigue el mismo caso).
            recent: Mensajes recientes del hilo, con las trazas del asistente.

        Returns:
            La evidencia y el nuevo estado del caso.
        """
        current = (
            case_from_recent(recent) if analysis.thread_action is ThreadAction.CONTINUE else None
        )
        if current is not None and current.motive in self._profiles:
            return self._select(query.text, current.motive, current)
        found = self._retriever.retrieve(EvidenceQuery(query.text))
        motive = found.items[0].entry.motive if found.items else ""
        if found.status is not RetrievalStatus.SUFFICIENT or motive not in self._profiles:
            return CaseRetrieval(found, None)
        return self._select(query.text, motive, None)

    def _select(self, text: str, motive: str, current: CaseState | None) -> CaseRetrieval:
        """Registro del cuadro en una de las etapas que permiten las reglas."""
        plan = plan_stages(current, self._profiles[motive].base_route)
        query = EvidenceQuery(text, motives=(motive,), stages=plan.stages, anchored=True)
        selected = self._retriever.retrieve(query)
        items = selected.items[: self._evidence_items]
        stage = items[0].entry.stage if items else None
        if selected.status is not RetrievalStatus.SUFFICIENT or stage is None:
            return CaseRetrieval(selected, current)
        return CaseRetrieval(replace(selected, items=items), advance(current, motive, stage))


def case_from_recent(recent: Sequence[ChatMessage]) -> CaseState | None:
    """Estado del caso guardado en la traza de la última respuesta del asistente que lo tenga.

    Returns:
        El estado, o None si ninguna respuesta reciente tiene cuadro (o la traza es inválida).
    """
    for message in reversed(recent):
        trace = message.trace
        if message.role is Role.ASSISTANT and trace is not None and trace.case_motive:
            return parse_case(trace.case_motive, trace.case_stage, trace.case_visited)
    return None


def parse_case(motive: str, stage: str, visited: Sequence[str]) -> CaseState | None:
    """Reconstruye el estado desde la traza (None si una etapa no es válida)."""
    try:
        return CaseState(motive, Stage(stage), tuple(Stage(item) for item in visited))
    except ValueError:
        return None
