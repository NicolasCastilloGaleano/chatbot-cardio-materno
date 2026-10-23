"""Pruebas del estado del caso y la evidencia por etapas (MIG-09 a MIG-13, ADR 0018)."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from cardio_materno.adapters.outbound.persistence.trace_codec import (
    trace_from_dict,
    trace_to_dict,
)
from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever
from cardio_materno.adapters.outbound.rag.knowledge_files import (
    KnowledgeBaseError,
    case_profile_to_dict,
    write_jsonl,
)
from cardio_materno.adapters.outbound.rag.vector_index import IndexManifest, VectorIndex
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.case_flow import CaseFlow, case_from_recent
from cardio_materno.application.evidence import EvidencePolicy, format_item
from cardio_materno.application.output_audit import closing_question, ensure_closing_question
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.bootstrap.rag_setup import load_profiles_for
from cardio_materno.bootstrap.settings import load_rag_settings
from cardio_materno.domain.case_state import (
    AFTER_INQUIRY_STAGES,
    INTENT_STAGES,
    CaseState,
    advance,
    plan_stages,
)
from cardio_materno.domain.conversation import ChatMessage, Domain, Role
from cardio_materno.domain.knowledge import RetrievalStatus, Route, Stage
from cardio_materno.domain.trace import ReplyTrace
from tests.unit.fakes import (
    CatalogRetriever,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    case_entry,
    case_profile,
    knowledge_entry,
)
from tests.unit.fakes import make_service as make_base_service

FEVER = "fiebre_bebe"
OTHER = "colico_lactante"
INQUIRY = (Stage.CHARACTERIZATION, Stage.CONTEXT, Stage.CASE_CHECK)


def case(*visited: Stage, motive: str = FEVER) -> CaseState:
    return CaseState(motive, visited[-1], visited)


def fever_catalog() -> CatalogRetriever:
    """Cuadro de fiebre completo (T1 es el más parecido) y un T1 de otro cuadro."""
    entries = [case_entry(FEVER, stage) for stage in Stage] + [
        case_entry(OTHER, Stage.DISCRIMINATORS)
    ]
    scores = {e.id: 0.6 for e in entries}
    scores[case_entry(FEVER, Stage.DISCRIMINATORS).id] = 0.8
    scores[case_entry(OTHER, Stage.DISCRIMINATORS).id] = 0.55
    for stage in INQUIRY:  # La siguiente etapa de indagación gana a las de intención.
        scores[case_entry(FEVER, stage).id] = 0.7
    return CatalogRetriever(entries, scores)


def analysis(action: ThreadAction = ThreadAction.CONTINUE) -> AnalysisTurn:
    return AnalysisTurn(action, Domain.MATERNAL_CHILD, "resumen")


def traced(state: CaseState) -> ChatMessage:
    trace = ReplyTrace(
        case_motive=state.motive,
        case_stage=str(state.stage),
        case_visited=tuple(str(s) for s in state.visited),
    )
    return ChatMessage(Role.ASSISTANT, "respuesta", trace=trace)


# --- Reglas de etapas (domain) -----------------------------------------------------------------


def test_new_case_starts_with_discriminators_or_an_explicit_intent() -> None:
    plan = plan_stages(None, Route.EMERGENCY)

    assert plan.stages == (Stage.DISCRIMINATORS, *INTENT_STAGES) and not plan.fixed
    assert Stage.EMERGENCY_TRANSFER not in plan.stages


def test_inquiry_advances_in_order_even_after_an_intent_jump() -> None:
    assert plan_stages(case(Stage.DISCRIMINATORS), Route.SELF_CARE).stages[0] is (
        Stage.CHARACTERIZATION
    )
    assert plan_stages(case(Stage.IMMEDIATE_ACTION), Route.SELF_CARE).stages[0] is (
        Stage.DISCRIMINATORS
    )


@pytest.mark.parametrize(
    ("route", "stage"),
    [
        (Route.SELF_CARE, Stage.IMMEDIATE_ACTION),
        (Route.PRIORITY_VISIT, Stage.PRIORITY_VISIT),
        (Route.EMERGENCY, Stage.EMERGENCY_TRANSFER),
    ],
)
def test_after_checking_the_case_the_base_route_decides(route: Route, stage: Stage) -> None:
    checked = case(Stage.DISCRIMINATORS, *INQUIRY)

    assert plan_stages(checked, route).stages == (stage,) and plan_stages(checked, route).fixed


def test_after_the_route_any_non_inquiry_stage_is_allowed() -> None:
    done = case(Stage.DISCRIMINATORS, *INQUIRY, Stage.IMMEDIATE_ACTION)

    assert plan_stages(done, Route.SELF_CARE).stages == AFTER_INQUIRY_STAGES


def test_advance_keeps_order_without_repeats_and_restarts_on_a_new_motive() -> None:
    state = advance(advance(None, FEVER, Stage.DISCRIMINATORS), FEVER, Stage.DISCRIMINATORS)

    assert state.visited == (Stage.DISCRIMINATORS,)
    assert advance(state, OTHER, Stage.CONTEXT) == CaseState(OTHER, Stage.CONTEXT, (Stage.CONTEXT,))


# --- Flujo del caso (application) --------------------------------------------------------------


def test_new_case_is_identified_in_both_domains_then_its_stage_is_chosen() -> None:
    retriever = fever_catalog()
    flow = CaseFlow(retriever, {FEVER: case_profile(FEVER), OTHER: case_profile(OTHER)}, 1)

    found = flow.retrieve(EvidenceQuery("fiebre", (Domain.CARDIOVASCULAR,)), analysis(), ())

    identify, select = retriever.queries
    assert identify == EvidenceQuery("fiebre")  # Sin el filtro de dominio del análisis.
    assert select.motives == (FEVER,) and select.anchored
    assert [i.entry.stage for i in found.result.items] == [Stage.DISCRIMINATORS]
    assert found.case == CaseState(FEVER, Stage.DISCRIMINATORS, (Stage.DISCRIMINATORS,))


def test_short_answer_in_a_case_gets_the_next_stage_without_identifying_again() -> None:
    retriever = fever_catalog()
    flow = CaseFlow(retriever, {FEVER: case_profile(FEVER)}, 1)

    found = flow.retrieve(
        EvidenceQuery("sí, desde ayer"), analysis(), [traced(case(Stage.DISCRIMINATORS))]
    )

    assert len(retriever.queries) == 1 and retriever.queries[0].anchored
    assert found.result.items[0].entry.stage is Stage.CHARACTERIZATION


def test_new_topic_identifies_the_case_again() -> None:
    retriever = fever_catalog()
    flow = CaseFlow(retriever, {FEVER: case_profile(FEVER)}, 1)
    recent = [traced(case(Stage.DISCRIMINATORS, *INQUIRY))]

    found = flow.retrieve(EvidenceQuery("otra cosa"), analysis(ThreadAction.NEW), recent)

    assert retriever.queries[0].motives == ()
    assert found.case is not None and found.case.visited == (Stage.DISCRIMINATORS,)


def test_without_enough_similarity_there_is_no_case() -> None:
    retriever = CatalogRetriever([case_entry(FEVER, Stage.DISCRIMINATORS)], {})
    flow = CaseFlow(retriever, {FEVER: case_profile(FEVER)}, 1)

    found = flow.retrieve(EvidenceQuery("hola"), analysis(), ())

    assert found.result.status is RetrievalStatus.INSUFFICIENT and found.case is None


def test_case_state_comes_from_the_last_assistant_trace_with_a_case() -> None:
    recent = [
        traced(case(Stage.DISCRIMINATORS)),
        ChatMessage(Role.ASSISTANT, "saludo", trace=ReplyTrace()),
    ]

    assert case_from_recent(recent) == case(Stage.DISCRIMINATORS)
    assert case_from_recent([ChatMessage(Role.USER, "hola")]) is None


# --- Auditor de salida -------------------------------------------------------------------------


def test_reply_without_a_question_gets_the_closing_question_of_its_entry() -> None:
    entry = case_entry(FEVER, Stage.IMMEDIATE_ACTION, "Ofrécele líquidos. ¿Cómo lo ves ahora?")

    assert closing_question(entry.answer) == "¿Cómo lo ves ahora?"
    assert ensure_closing_question("Ofrécele líquidos.", [entry]) == (
        "Ofrécele líquidos. ¿Cómo lo ves ahora?"
    )
    assert ensure_closing_question("¿Tiene fiebre?", [entry]) == "¿Tiene fiebre?"
    assert ensure_closing_question("Sin pregunta.", [knowledge_entry()]) == "Sin pregunta."


# --- Conversación completa con la base v2 ------------------------------------------------------


def answer_of(stage: Stage) -> str:
    return case_entry(FEVER, stage).answer


def test_conversation_inquires_first_and_then_follows_the_base_route() -> None:
    expected = [Stage.DISCRIMINATORS, *INQUIRY, Stage.EMERGENCY_TRANSFER]
    agent = ScriptedAgent(*(agent_json(answer_of(stage)) for stage in expected))
    retriever = fever_catalog()
    service = make_base_service(
        agent,
        InMemoryThreadRepository(),
        {"case_profiles": {FEVER: case_profile(FEVER, Route.EMERGENCY)}},
        retriever,
    )

    results = [
        service.send(text) for text in ("mi bebé tiene fiebre", "sí", "no", "ayer", "así es")
    ]

    assert [r.trace.case_stage for r in results if r.trace] == [str(s) for s in expected]
    assert [r.reply for r in results] == [answer_of(stage) for stage in expected]
    assert sum(1 for q in retriever.queries if not q.anchored) == 1


def test_reply_that_drops_the_question_is_completed_by_the_auditor() -> None:
    entry = case_entry(
        FEVER, Stage.DISCRIMINATORS, "Ofrécele líquidos. ¿Desde cuándo tiene fiebre?"
    )
    retriever = CatalogRetriever([entry], {entry.id: 0.9})
    agent = ScriptedAgent(agent_json("Ofrécele líquidos."))
    service = make_base_service(
        agent,
        InMemoryThreadRepository(),
        {"case_profiles": {FEVER: case_profile(FEVER)}},
        retriever,
    )

    assert service.send("fiebre").reply == "Ofrécele líquidos. ¿Desde cuándo tiene fiebre?"


def test_case_state_round_trips_through_the_trace_json() -> None:
    trace = traced(case(Stage.DISCRIMINATORS, Stage.CHARACTERIZATION)).trace
    assert trace is not None

    assert trace_from_dict(trace_to_dict(trace)) == trace
    assert "case" not in trace_to_dict(ReplyTrace())


# --- Buscador y arranque -----------------------------------------------------------------------


class CountingEmbedder:
    model = "m"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


def test_retriever_filters_by_case_and_stage_and_embeds_a_repeated_text_once() -> None:
    entries = [case_entry(FEVER, s) for s in (Stage.DISCRIMINATORS, Stage.CONTEXT)] + [
        case_entry(OTHER, Stage.DISCRIMINATORS)
    ]
    matrix = np.asarray([[1.0, 0.0], [0.2, 1.0], [1.0, 0.1]], dtype=np.float32)
    index = VectorIndex([e.id for e in entries], matrix, IndexManifest("m", 2, "h", "hoy", 3))
    embedder = CountingEmbedder()
    retriever = HybridRetriever(entries, index, embedder, EvidencePolicy(min_similarity=0.5))

    anchored = EvidenceQuery("x", motives=(FEVER,), stages=(Stage.CONTEXT,), anchored=True)
    strict = EvidenceQuery("x", motives=(FEVER,), stages=(Stage.CONTEXT,))

    assert [i.entry.stage for i in retriever.retrieve(anchored).items] == [Stage.CONTEXT]
    assert retriever.retrieve(strict).status is RetrievalStatus.INSUFFICIENT
    assert embedder.calls == 1


def test_evidence_header_shows_the_stage() -> None:
    item = (
        CatalogRetriever([case_entry(FEVER, Stage.CONTEXT)], {})
        .retrieve(EvidenceQuery("x", anchored=True))
        .items[0]
    )

    assert "etapa T3_contexto" in format_item(item, 700)


def test_profiles_are_loaded_only_for_a_base_with_cases(tmp_path: Path) -> None:
    path = tmp_path / "cuadros.jsonl"
    v2 = [case_entry(FEVER, Stage.DISCRIMINATORS)]

    assert load_profiles_for([knowledge_entry()], path) == {}
    with pytest.raises(KnowledgeBaseError):
        load_profiles_for(v2, path)
    write_jsonl([case_profile_to_dict(case_profile(OTHER))], path)
    with pytest.raises(KnowledgeBaseError, match=FEVER):
        load_profiles_for(v2, path)
    write_jsonl([case_profile_to_dict(case_profile(FEVER))], path)
    assert set(load_profiles_for(v2, path)) == {FEVER}


def test_cases_file_setting_has_a_default_and_can_be_changed(tmp_path: Path) -> None:
    assert load_rag_settings({}, tmp_path).cases_file == tmp_path / "knowledge/kb/cuadros.jsonl"
    custom = load_rag_settings({"KB_CASES_FILE": "data/kb_v2/cuadros.jsonl"}, tmp_path)
    assert custom.cases_file == tmp_path / "data/kb_v2/cuadros.jsonl"
