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
from cardio_materno.domain.trace import InquiryTrace, ModelUsage, TurnMode
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


def test_inquiry_is_not_evaluated_when_the_message_is_not_about_health() -> None:
    """Guion del 2026-10-27: "gracias" en el hilo de la presión salía "indagar"."""
    thanks = agent_json("Gracias por escribirme.") | {"about_health": False}

    (result,) = send_all(OBSERVE, FakeRetriever(promising()), thanks)

    assert result.trace is not None and result.trace.inquiry is None
    assert result.trace.about_health is False


def test_contradictory_unrelated_message_in_a_thread_is_answered_as_conversational() -> None:
    """En vivo (2026-10-28): el análisis dejó el partido en_alcance pero no de salud."""
    fever = agent_json("¿Desde cuándo?", thread_action="nuevo", reported_symptoms=["fiebre"])
    match = agent_json(
        "Sobre eso no puedo ayudarte.", summary="El partido", reported_symptoms=["fiebre"]
    ) | {"about_health": False}
    retriever = FakeRetriever(promising())
    service = make_service(ScriptedAgent(fever, match), config=OBSERVE, retriever=retriever)

    service.send("mi bebé tiene fiebre")
    result = service.send("¿quién ganó el partido?")

    assert result.trace is not None and result.trace.scope == "conversacional"
    assert result.trace.inquiry is None and len(retriever.queries) == 1
    assert result.thread is not None and result.thread.summary == "resumen"


def test_model_usage_of_each_stage_reaches_the_trace() -> None:
    agent = ScriptedAgent(agent_json("respuesta"))
    agent.analyzer.usage = ModelUsage("", 3700, 40.0, 210, 12.5)
    agent.responder.usage = ModelUsage("", 900, 3.0, 80, 5.0)
    service = make_service(agent, retriever=FakeRetriever(promising()))

    result = service.send("me duele el brazo")

    assert result.trace is not None
    assert result.trace.model_usage == (
        ModelUsage("análisis", 3700, 40.0, 210, 12.5),
        ModelUsage("respuesta", 900, 3.0, 80, 5.0),
    )


def test_console_debug_line_shows_the_observed_mode() -> None:
    inquiry = InquiryTrace(TurnMode.INQUIRE, 1, 0, 0.55, 0.03, 2, "Acidez", None, True)

    assert format_inquiry_debug(inquiry) == (
        "[indagación observada: indagar · turno 1 · s1 0.55 · margen 0.03"
        " · coincidencia 2 (Acidez) · avance — · pide orientación]"
    )
