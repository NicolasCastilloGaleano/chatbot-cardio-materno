"""Pruebas de la indagación en modo observar dentro del servicio (HU-11, fase 2, ADR 0017).

En modo `observar` la regla calcula el modo del turno y lo guarda en la traza, pero la
respuesta es exactamente la de antes. El estado del turno siguiente sale de esa traza.
"""

from dataclasses import replace
from typing import Any

from cardio_materno.adapters.inbound.console.debug_lines import format_inquiry_debug
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.inquiry_policy import InquiryActivation
from cardio_materno.domain.knowledge import EvidenceItem, RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import InquiryTrace, TurnMode
from tests.unit.fakes import (
    FakeRetriever,
    ScriptedAgent,
    agent_json,
    evidence_result,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    signing,
)

OBSERVE = {"inquiry_activation": InquiryActivation.OBSERVE}


def promising(score: float = 0.55, category: str = "Acidez") -> RetrievalResult:
    """Resultado con evidencia y un candidato entre el piso y el umbral para responder."""
    entry = replace(knowledge_entry(answer="respuesta"), category=category)
    found = evidence_result(entry)
    return replace(found, candidates=(EvidenceItem("C1", entry, score),), best_score=score)


def send_all(
    config: dict[str, Any], retriever: FakeRetriever, *turns: dict[str, Any]
) -> list[TurnResult]:
    service = make_service(ScriptedAgent(*turns), config=config, retriever=retriever)
    return [service.send(f"mensaje {n}") for n, _ in enumerate(turns, start=1)]


def inquiry_of(result: TurnResult) -> InquiryTrace:
    assert result.trace is not None and result.trace.inquiry is not None
    return result.trace.inquiry


def test_observe_records_the_mode_without_changing_the_reply() -> None:
    (observed,) = send_all(OBSERVE, FakeRetriever(promising()), agent_json("respuesta"))
    (plain,) = send_all({}, FakeRetriever(promising()), agent_json("respuesta"))

    assert observed.reply == plain.reply == "respuesta"
    assert inquiry_of(observed) == InquiryTrace(
        TurnMode.INQUIRE, 1, 0, 0.55, 0.55, 1, "Acidez", None, False, applied=False
    )
    assert plain.trace is not None and plain.trace.inquiry is None


def test_the_next_turn_of_the_thread_reads_the_previous_inquiry() -> None:
    turns = (agent_json("respuesta", thread_action="nuevo"), agent_json("respuesta"))

    first, second = send_all(OBSERVE, FakeRetriever(promising(0.55), promising(0.58)), *turns)

    assert (inquiry_of(first).turn, inquiry_of(second).turn) == (1, 2)
    assert inquiry_of(second).progress is True


def test_a_new_topic_restarts_the_inquiry() -> None:
    turns = (agent_json("respuesta", thread_action="nuevo"),) * 2

    _, second = send_all(OBSERVE, FakeRetriever(promising()), *turns)

    assert (inquiry_of(second).turn, inquiry_of(second).progress) == (1, None)


def test_direct_request_for_guidance_is_recorded() -> None:
    turn = agent_json("respuesta") | {"wants_guidance": True}

    (result,) = send_all(OBSERVE, FakeRetriever(promising(0.52)), turn)

    assert inquiry_of(result).mode is TurnMode.ANSWER and inquiry_of(result).wants_guidance


def test_without_evidence_the_abstention_is_kept_and_the_mode_recorded() -> None:
    nothing = RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.3)

    (result,) = send_all(OBSERVE, FakeRetriever(nothing), agent_json())

    assert inquiry_of(result).mode is TurnMode.ABSTAIN
    assert "No tengo información validada" in result.reply


def test_inquiry_is_not_evaluated_with_a_new_alarm_or_without_the_retriever() -> None:
    config = OBSERVE | {"alarm_policy": make_alarm_policy()}
    alarm = signing(agent_json("respuesta"), "PRESION_ALTA")
    unavailable = FakeRetriever(RetrievalResult(RetrievalStatus.UNAVAILABLE))

    (with_alarm,) = send_all(config, FakeRetriever(promising()), alarm)
    (without_rag,) = send_all(OBSERVE, unavailable, agent_json())

    assert with_alarm.trace is not None and with_alarm.trace.inquiry is None
    assert without_rag.trace is not None and without_rag.trace.inquiry is None


def test_console_debug_line_shows_the_observed_mode() -> None:
    inquiry = InquiryTrace(TurnMode.INQUIRE, 1, 0, 0.55, 0.03, 2, "Acidez", None, True)

    assert format_inquiry_debug(inquiry) == (
        "[indagación observada: indagar · turno 1 · s1 0.55 · margen 0.03"
        " · coincidencia 2 (Acidez) · avance — · pide orientación]"
    )
