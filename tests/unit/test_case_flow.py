"""Pruebas de la identificación del cuadro y la elección de su registro (MIG-10, ADR 0018)."""

from collections.abc import Sequence

import numpy as np

from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.vector_index import IndexManifest, VectorIndex
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.case_flow import CaseFlow
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.case_state import CaseState, pending_stages
from cardio_materno.domain.conversation import ChatMessage, Domain, Role
from cardio_materno.domain.knowledge import RetrievalStatus, Stage
from cardio_materno.domain.trace import ReplyTrace
from tests.unit.fakes import CatalogRetriever, case_entry, case_profile

FEVER = "fiebre_bebe"
OTHER = "colico_lactante"
T1, T2, T3 = Stage.DISCRIMINATORS, Stage.CHARACTERIZATION, Stage.CONTEXT


def fever_catalog() -> CatalogRetriever:
    """Cuadro de fiebre completo (T1 el más parecido, T3 el segundo) y un T1 de otro cuadro."""
    entries = [case_entry(FEVER, stage) for stage in Stage] + [case_entry(OTHER, T1)]
    scores = {e.id: 0.6 for e in entries}
    scores |= {case_entry(FEVER, T1).id: 0.8, case_entry(FEVER, T3).id: 0.7}
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


def test_pending_stages_skip_the_visited_ones_and_restart_when_all_were_shown() -> None:
    assert pending_stages(None) == tuple(Stage)
    assert T1 not in pending_stages(CaseState(FEVER, T1, (T1,)))
    assert pending_stages(CaseState(FEVER, T1, tuple(Stage))) == tuple(Stage)


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


def test_short_answer_keeps_the_case_and_gets_a_stage_not_shown_yet() -> None:
    retriever = fever_catalog()

    found = flow(retriever).retrieve(EvidenceQuery("sí, desde ayer"), analysis(), [traced(T1)])

    assert len(retriever.queries) == 1 and retriever.queries[0].anchored
    assert T1 not in retriever.queries[0].stages
    assert found.result.items[0].entry.stage is T3
    assert found.case == CaseState(FEVER, T3, (T1, T3))


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
