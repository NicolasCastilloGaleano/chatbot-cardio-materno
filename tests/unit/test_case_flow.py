"""Pruebas del cuadro, sus etapas y la elección de su registro (MIG-10 y MIG-11, ADR 0018)."""

from collections.abc import Sequence

import numpy as np
import pytest

from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.vector_index import IndexManifest, VectorIndex
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.case_flow import CaseFlow
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.case_state import (
    AFTER_INQUIRY_STAGES,
    INQUIRY_SEQUENCE,
    INTENT_STAGES,
    CaseState,
    plan_stages,
)
from cardio_materno.domain.conversation import ChatMessage, Domain, Role
from cardio_materno.domain.knowledge import RetrievalStatus, Route, Stage
from cardio_materno.domain.trace import ReplyTrace
from tests.unit.fakes import (
    CatalogRetriever,
    ScriptedAgent,
    agent_json,
    case_entry,
    case_profile,
    make_service,
)

FEVER = "fiebre_bebe"
OTHER = "colico_lactante"
T1, T2, T3 = Stage.DISCRIMINATORS, Stage.CHARACTERIZATION, Stage.CONTEXT


def fever_catalog() -> CatalogRetriever:
    """Cuadro de fiebre completo y un T1 de otro cuadro.

    T1 es el más parecido; las demás etapas de indagación ganan a las de intención, y T3 es
    más parecida que T2.
    """
    entries = [case_entry(FEVER, stage) for stage in Stage] + [case_entry(OTHER, T1)]
    scores = {e.id: 0.6 for e in entries}
    scores |= {case_entry(FEVER, stage).id: 0.7 for stage in INQUIRY_SEQUENCE}
    scores |= {case_entry(FEVER, T1).id: 0.8, case_entry(FEVER, T3).id: 0.75}
    scores[case_entry(OTHER, T1).id] = 0.55
    return CatalogRetriever(entries, scores)


def analysis(action: ThreadAction = ThreadAction.CONTINUE) -> AnalysisTurn:
    return AnalysisTurn(action, Domain.MATERNAL_CHILD, "resumen")


def traced(*visited: Stage, motive: str = FEVER) -> ChatMessage:
    trace = ReplyTrace(
        case_motive=motive,
        case_stage=str(visited[-1]),
        case_visited=tuple(str(s) for s in visited),
    )
    return ChatMessage(Role.ASSISTANT, "respuesta", trace=trace)


def flow(retriever: CatalogRetriever) -> CaseFlow:
    return CaseFlow(retriever, {FEVER: case_profile(FEVER), OTHER: case_profile(OTHER)}, 1)


# --- Dominio -----------------------------------------------------------------------------------


def state(*visited: Stage) -> CaseState:
    return CaseState(FEVER, visited[-1], visited)


def test_new_case_starts_with_discriminators_or_an_explicit_intent() -> None:
    plan = plan_stages(None, Route.EMERGENCY)

    assert plan.stages == (T1, *INTENT_STAGES) and not plan.fixed
    assert Stage.EMERGENCY_TRANSFER not in plan.stages


def test_inquiry_advances_in_order_even_after_an_intent_jump() -> None:
    assert plan_stages(state(T1), Route.SELF_CARE).stages[0] is T2
    after_jump = plan_stages(state(Stage.IMMEDIATE_ACTION), Route.SELF_CARE).stages
    assert after_jump[0] is T1 and Stage.IMMEDIATE_ACTION not in after_jump


@pytest.mark.parametrize(
    ("route", "stage"),
    [
        (Route.SELF_CARE, Stage.IMMEDIATE_ACTION),
        (Route.PRIORITY_VISIT, Stage.PRIORITY_VISIT),
        (Route.EMERGENCY, Stage.EMERGENCY_TRANSFER),
    ],
)
def test_after_checking_the_case_the_base_route_decides(route: Route, stage: Stage) -> None:
    plan = plan_stages(state(*INQUIRY_SEQUENCE), route)

    assert plan.stages == (stage,) and plan.fixed


def test_after_the_route_only_unseen_non_inquiry_stages_are_allowed() -> None:
    done = state(*INQUIRY_SEQUENCE, Stage.IMMEDIATE_ACTION)

    stages = plan_stages(done, Route.SELF_CARE).stages
    assert Stage.IMMEDIATE_ACTION not in stages
    assert set(stages) == set(AFTER_INQUIRY_STAGES) - {Stage.IMMEDIATE_ACTION}
    assert plan_stages(state(*Stage), Route.SELF_CARE).stages == AFTER_INQUIRY_STAGES


# --- Flujo del caso ----------------------------------------------------------------------------


def test_new_case_is_identified_in_both_domains_with_a_single_entry() -> None:
    retriever = fever_catalog()

    found = flow(retriever).retrieve(
        EvidenceQuery("fiebre", (Domain.CARDIOVASCULAR,)), analysis(), ()
    )

    identify, select = retriever.queries
    assert identify == EvidenceQuery("fiebre")  # Sin el filtro de dominio del análisis.
    assert select.motives == (FEVER,) and select.anchored
    assert [i.entry.stage for i in found.result.items] == [T1]
    assert found.case == CaseState(FEVER, T1, (T1,))


def test_short_answer_keeps_the_case_and_gets_the_next_inquiry_stage() -> None:
    retriever = fever_catalog()  # T3 es más parecida que T2, pero aún no le toca.

    found = flow(retriever).retrieve(EvidenceQuery("sí, desde ayer"), analysis(), [traced(T1)])

    assert len(retriever.queries) == 1 and retriever.queries[0].anchored
    assert retriever.queries[0].stages == (T2, *INTENT_STAGES)
    assert found.result.items[0].entry.stage is T2
    assert found.case == CaseState(FEVER, T2, (T1, T2))


def test_new_topic_identifies_the_case_again() -> None:
    retriever = fever_catalog()

    found = flow(retriever).retrieve(
        EvidenceQuery("otra cosa"), analysis(ThreadAction.NEW), [traced(T1, T2)]
    )

    assert retriever.queries[0].motives == ()
    assert found.case == CaseState(FEVER, T1, (T1,))


def test_without_enough_similarity_there_is_no_case() -> None:
    retriever = CatalogRetriever([case_entry(FEVER, T1)], {})

    found = flow(retriever).retrieve(EvidenceQuery("hola"), analysis(), ())

    assert found.result.status is RetrievalStatus.INSUFFICIENT and found.case is None


def test_conversation_inquires_first_and_then_follows_the_base_route() -> None:
    expected = [*INQUIRY_SEQUENCE, Stage.EMERGENCY_TRANSFER]
    agent = ScriptedAgent(*(agent_json(case_entry(FEVER, stage).answer) for stage in expected))
    retriever = fever_catalog()
    config = {"case_profiles": {FEVER: case_profile(FEVER, Route.EMERGENCY)}}
    service = make_service(agent, config=config, retriever=retriever)

    results = [
        service.send(text) for text in ("mi bebé tiene fiebre", "sí", "no", "ayer", "así es")
    ]

    assert [r.trace.case_stage for r in results if r.trace] == [str(s) for s in expected]
    assert [r.reply for r in results] == [case_entry(FEVER, s).answer for s in expected]
    assert sum(1 for q in retriever.queries if not q.anchored) == 1


# --- Buscador ----------------------------------------------------------------------------------


class CountingEmbedder:
    model = "m"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


def test_retriever_filters_by_case_and_stage_and_embeds_a_repeated_text_once() -> None:
    entries = [case_entry(FEVER, s) for s in (T1, T3)] + [case_entry(OTHER, T1)]
    matrix = np.asarray([[1.0, 0.0], [0.2, 1.0], [1.0, 0.1]], dtype=np.float32)
    index = VectorIndex([e.id for e in entries], matrix, IndexManifest("m", 2, "h", "hoy", 3))
    embedder = CountingEmbedder()
    retriever = HybridRetriever(entries, index, embedder, EvidencePolicy(min_similarity=0.5))

    anchored = EvidenceQuery("x", motives=(FEVER,), stages=(T3,), anchored=True)
    strict = EvidenceQuery("x", motives=(FEVER,), stages=(T3,))

    assert [i.entry.stage for i in retriever.retrieve(anchored).items] == [T3]
    assert retriever.retrieve(strict).status is RetrievalStatus.INSUFFICIENT
    assert embedder.calls == 1
