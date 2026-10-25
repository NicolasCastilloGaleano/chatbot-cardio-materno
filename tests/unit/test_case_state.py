"""Pruebas del estado del caso con la base v2 (MIG-09, ADR 0018)."""

from cardio_materno.adapters.inbound.api.serializers import case_snapshot
from cardio_materno.adapters.inbound.console.debug_lines import format_case_debug
from cardio_materno.adapters.outbound.persistence.trace_codec import (
    trace_from_dict,
    trace_to_dict,
)
from cardio_materno.application.case_flow import case_from_recent, parse_case
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.case_state import CaseState, advance
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.knowledge import RetrievalResult, Stage
from cardio_materno.domain.trace import ReplyTrace
from tests.unit.fakes import (
    ScriptedAgent,
    agent_json,
    case_entry,
    evidence_result,
    make_service,
    thread_of,
)

FEVER = "fiebre_bebe"
COLIC = "colico_lactante"
T1, T2 = Stage.DISCRIMINATORS, Stage.CHARACTERIZATION


def case_trace(motive: str = FEVER, stage: str = "T1_discriminantes") -> ReplyTrace:
    return ReplyTrace(case_motive=motive, case_stage=stage, case_visited=(stage,))


def assistant(trace: ReplyTrace | None) -> ChatMessage:
    return ChatMessage(Role.ASSISTANT, "r", "h", None, trace)


# --- Dominio -----------------------------------------------------------------------------------


def test_advance_adds_new_stages_once_and_restarts_on_another_case() -> None:
    first = advance(None, FEVER, T1)
    second = advance(first, FEVER, T2)

    assert second == CaseState(FEVER, T2, (T1, T2))
    assert advance(second, FEVER, T1) == CaseState(FEVER, T1, (T1, T2))
    assert advance(second, COLIC, T2) == CaseState(COLIC, T2, (T2,))


# --- Lectura desde el hilo ---------------------------------------------------------------------


def test_case_is_read_from_the_latest_assistant_reply_that_has_one() -> None:
    recent = [
        assistant(case_trace(stage="T1_discriminantes")),
        ChatMessage(Role.USER, "sí", "h", None),
        assistant(ReplyTrace()),
    ]

    assert case_from_recent(recent) == CaseState(FEVER, T1, (T1,))
    assert case_from_recent([assistant(None)]) is None


def test_invalid_stage_in_a_trace_is_ignored() -> None:
    assert parse_case(FEVER, "T9", ["T9"]) is None


# --- Persistencia y presentación ---------------------------------------------------------------


def test_trace_codec_keeps_the_case_and_reads_old_traces() -> None:
    trace = case_trace()

    assert trace_from_dict(trace_to_dict(trace)) == trace
    assert "case" not in trace_to_dict(ReplyTrace())
    assert trace_from_dict(trace_to_dict(ReplyTrace())).case_motive == ""


def test_case_is_shown_in_the_panel_and_the_debug_lines() -> None:
    assert case_snapshot(ReplyTrace()) is None
    assert case_snapshot(case_trace())["motive"] == FEVER  # type: ignore[index]
    assert format_case_debug(ReplyTrace()) == ""
    assert FEVER in format_case_debug(case_trace())


# --- Conversación ------------------------------------------------------------------------------


class StageRetriever:
    """Devuelve, turno a turno, un registro v2 que respalda la respuesta guionizada."""

    def __init__(self, agent: ScriptedAgent, *stages: tuple[str, Stage]) -> None:
        self._agent = agent
        self._stages = list(stages)

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        motive, stage = self._stages.pop(0)
        return evidence_result(case_entry(motive, stage, answer=self._agent.reply_text))


def converse(agent: ScriptedAgent, *stages: tuple[str, Stage]) -> list[ReplyTrace | None]:
    """Envía un mensaje por cada etapa en el mismo servicio (mismo hilo)."""
    service = make_service(agent, retriever=StageRetriever(agent, *stages))
    return [service.send("mensaje").trace for _ in stages]


def test_the_case_accumulates_the_stages_shown_in_a_thread() -> None:
    agent = ScriptedAgent(agent_json("Primera."), agent_json("Segunda."))

    first, second = converse(agent, (FEVER, T1), (FEVER, T2))

    assert first is not None and first.case_visited == ("T1_discriminantes",)
    assert second is not None and second.case_motive == FEVER
    assert second.case_visited == ("T1_discriminantes", "T2_caracterizacion")


def test_a_new_topic_starts_a_new_case() -> None:
    agent = ScriptedAgent(agent_json("Primera."), agent_json("Segunda.", thread_action="nuevo"))

    _, second = converse(agent, (FEVER, T1), (COLIC, T2))

    assert second is not None and second.case_motive == COLIC
    assert second.case_visited == ("T2_caracterizacion",)


def test_base_v1_replies_have_no_case() -> None:
    result = make_service(ScriptedAgent(agent_json("r"))).send("tengo acidez")

    assert result.trace is not None and result.trace.case_motive == ""
    assert thread_of(result) is not None
