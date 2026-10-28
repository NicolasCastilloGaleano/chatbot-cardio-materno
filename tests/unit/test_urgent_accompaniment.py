"""Pruebas del acompañamiento de una urgencia ya avisada (B-030, ADR 0018, 2026-10-28)."""

from dataclasses import replace
from typing import Any

from cardio_materno.adapters.inbound.console.debug_lines import (
    URGENT_ACCOMPANIMENT_DEBUG_TEXT,
    trace_lines,
)
from cardio_materno.application.alarm_policy import (
    REMINDER_MESSAGES,
    REPLY_SEPARATOR,
    URGENT_ACCOMPANIMENT_CONTEXT,
)
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.inquiry_policy import InquiryActivation
from cardio_materno.domain.alarms import Severity
from cardio_materno.domain.knowledge import EvidenceItem, RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import ReplyTrace
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

URGENT = REMINDER_MESSAGES[Severity.IMMEDIATE]
PRIORITY = REMINDER_MESSAGES[Severity.PRIORITY]
CONFIG = {"alarm_policy": make_alarm_policy(), "inquiry_activation": InquiryActivation.ACTIVE}
WHILE_ARRIVING = "Ve acompañada y lleva tu carné prenatal. ¿Cuántas semanas tienes?"


def bleeding_then(follow_up: dict[str, Any], retriever: FakeRetriever) -> tuple[TurnResult, str]:
    """Urgencia por el filtro 1 y, en el mismo hilo, un mensaje en que el filtro 2 la recuerda.

    Returns:
        El segundo turno y el contexto que recibió la llamada de respuesta ("" si no se hizo).
    """
    agent = ScriptedAgent(signing(follow_up, "SANGRADO_VAGINAL"))
    service = make_service(agent, config=CONFIG, retriever=retriever)
    service.send("tengo sangrado vaginal")
    result = service.send("¿qué hago mientras llego?")
    calls = agent.responder.calls
    return result, "\n".join(m.content for m in calls[0]) if calls else ""


def trace_of(result: TurnResult) -> ReplyTrace:
    assert result.trace is not None
    return result.trace


def test_urgent_reminder_is_followed_by_guidance_without_questions() -> None:
    sentences = [
        {"text": "Ve acompañada y lleva tu carné prenatal.", "evidence_id": "E1"},
        {"text": "¿Cuántas semanas tienes?", "evidence_id": "E1"},
    ]
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=WHILE_ARRIVING)))

    result, context = bleeding_then(agent_json("x") | {"sentences": sentences}, retriever)

    trace = trace_of(result)
    assert result.reply == f"{URGENT}{REPLY_SEPARATOR}Ve acompañada y lleva tu carné prenatal."
    assert URGENT_ACCOMPANIMENT_CONTEXT in context
    assert trace.urgent_accompaniment and trace.inquiry is None
    assert trace.grounding is not None
    assert trace.grounding.dropped == ("¿Cuántas semanas tienes?",)


def test_literal_text_also_drops_the_questions() -> None:
    sentences = [{"text": "Toma ibuprofeno.", "evidence_id": "E1"}]
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=WHILE_ARRIVING)))

    result, _ = bleeding_then(agent_json("x") | {"sentences": sentences}, retriever)

    assert "¿Cuántas semanas" not in result.reply and "Ve acompañada" in result.reply


def test_without_evidence_only_the_reminder_is_shown() -> None:
    nothing = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.3))

    result, _ = bleeding_then(agent_json("x"), nothing)

    assert result.reply == URGENT and trace_of(result).urgent_accompaniment


def test_a_priority_reminder_can_still_be_inquired() -> None:
    entry = knowledge_entry(answer="respuesta")
    promising = replace(
        evidence_result(entry), candidates=(EvidenceItem("C1", entry, 0.55),), best_score=0.55
    )
    agent = ScriptedAgent(
        agent_json("r", thread_action="nuevo"),
        signing(agent_json("r") | {"questions": ["¿Qué comes a diario?"]}, "PRESION_ALTA"),
    )
    service = make_service(agent, config=CONFIG, retriever=FakeRetriever(promising))
    service.send("tengo presion alta")

    result = service.send("¿qué puedo comer?")

    assert result.reply == f"{PRIORITY}{REPLY_SEPARATOR}¿Qué comes a diario?"
    assert not trace_of(result).urgent_accompaniment


def test_console_shows_the_urgent_accompaniment() -> None:
    nothing = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.3))

    result, _ = bleeding_then(agent_json("x"), nothing)

    assert URGENT_ACCOMPANIMENT_DEBUG_TEXT in trace_lines(trace_of(result))
