"""Pruebas de la orientación después del aviso de una urgencia (B-034, ADR 0021)."""

from typing import Any

import pytest

from cardio_materno.adapters.inbound.console.console_chat import ASSISTANT_LABEL, ConsoleChat
from cardio_materno.application.conversation_service import (
    URGENT_GUIDANCE_QUESTION,
    URGENT_GUIDANCE_TEMPLATE,
    ConversationService,
    TurnResult,
    UrgentGuidanceActivation,
    UrgentGuidanceRequest,
    urgency_analysis,
    urgency_query,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence_selection import SelectionActivation
from cardio_materno.domain.conversation import Role
from cardio_materno.domain.knowledge import Focus, RetrievalResult, RetrievalStatus
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeRetriever,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    evidence_result,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    selecting,
)

BLEEDING = "tengo sangrado vaginal"
ENTRY = "Pide ayuda para el traslado. No retrases la salida."
USEFUL = "Pide ayuda para el traslado."
ON: dict[str, Any] = {
    "alarm_policy": make_alarm_policy(),
    "selection_activation": SelectionActivation.ACTIVE,
    "selection_prompt": "SELECTOR",
    "selected_reply_prompt": "REDACTOR",
    "urgent_guidance": UrgentGuidanceActivation.ACTIVE,
}


def service_for(
    agent: ScriptedAgent, repo: InMemoryThreadRepository, **config: Any
) -> ConversationService:
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=ENTRY)))
    return make_service(agent, repo, config=ON | config, retriever=retriever)


def alarm_turn(**config: Any) -> tuple[TurnResult, ConversationService, ScriptedAgent, Any]:
    """Aviso de una urgencia del filtro 1, que no consulta al agente."""
    agent = ScriptedAgent()
    repo = InMemoryThreadRepository()
    service = service_for(agent, repo, **config)
    return service.send(BLEEDING), service, agent, repo


def request_of(result: TurnResult) -> UrgentGuidanceRequest:
    assert result.urgent_guidance is not None
    return result.urgent_guidance


def guide(turn: dict[str, Any]) -> tuple[TurnResult | None, ScriptedAgent, Any]:
    result, service, agent, repo = alarm_turn()
    agent.current = turn
    return service.guide(request_of(result)), agent, repo


# --- El aviso no cambia --------------------------------------------------------------------------


def test_the_notice_does_not_wait_for_the_model() -> None:
    result, _, agent, _ = alarm_turn()

    assert result.reply == URGENT_MESSAGE
    assert agent.responder.calls == [] and agent.analyzer.calls == []
    assert request_of(result).analysis is None


def test_turned_off_there_is_no_guidance() -> None:
    result, *_ = alarm_turn(urgent_guidance=UrgentGuidanceActivation.OFF)

    assert result.urgent_guidance is None


def test_without_the_active_selector_there_is_no_guidance() -> None:
    result, *_ = alarm_turn(selection_activation=SelectionActivation.OBSERVE)

    assert result.urgent_guidance is None


def test_only_the_first_notice_of_a_rule_in_the_thread_is_guided() -> None:
    _, service, _, _ = alarm_turn()

    assert service.send(BLEEDING).urgent_guidance is None


# --- La orientación ------------------------------------------------------------------------------


def test_guidance_is_a_verified_message_in_the_same_thread() -> None:
    guided, agent, repo = guide(selecting(agent_json(USEFUL), "responde", "E1.1"))

    assert guided is not None
    assert guided.reply == URGENT_GUIDANCE_TEMPLATE.format(text=USEFUL)
    assert guided.trace is not None and guided.trace.urgent_follow_up
    assert guided.trace.selection is not None and guided.trace.selection.applied
    assert [call[0].content for call in agent.responder.calls] == ["SELECTOR", "REDACTOR"]
    messages = repo.messages[guided.thread.id] if guided.thread else []
    assert messages[-1].role is Role.ASSISTANT and messages[-1].content == guided.reply
    assert len(repo.alerts[guided.thread.id] if guided.thread else []) == 1


def test_the_case_comes_from_the_rule_when_there_was_no_analysis() -> None:
    _, agent, _ = guide(selecting(agent_json(USEFUL), "responde", "E1.1"))

    context = "\n".join(message.content for message in agent.responder.calls[0])
    assert "URGENCIA EN CURSO" in context
    assert "reported_symptoms" in context
    assert BLEEDING in context


def test_the_selector_is_asked_what_to_do_now_and_not_about_the_symptom() -> None:
    result, service, agent, _ = alarm_turn()
    agent.current = selecting(agent_json(USEFUL), "responde", "E1.1")
    request = request_of(result)

    service.guide(request)

    assert agent.responder.calls[0][-1].content == URGENT_GUIDANCE_QUESTION
    query = urgency_query(request, urgency_analysis(request))
    assert query.text.startswith("qué hacer mientras llega a urgencias")
    assert BLEEDING in query.text and request.decision.primary_rule.sign in query.text
    assert query.focus is Focus.SOLVE


def test_general_actions_of_a_partial_record_are_shown_in_an_urgency() -> None:
    guided, *_ = guide(selecting(agent_json(USEFUL), "parcial", "E1.1", fit="en_parte"))

    assert guided is not None and USEFUL in guided.reply


def test_nothing_is_sent_without_useful_content(caplog: pytest.LogCaptureFixture) -> None:
    guided, _, repo = guide(selecting(agent_json("x"), "no_responde"))

    assert guided is None
    assert "sin frases visibles (no_responde" in caplog.text
    assert all(len(messages) == 2 for messages in repo.messages.values())


def test_the_log_says_how_close_the_search_was(caplog: pytest.LogCaptureFixture) -> None:
    retriever = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.42))
    service = make_service(
        ScriptedAgent(), InMemoryThreadRepository(), config=ON, retriever=retriever
    )

    assert service.guide(request_of(service.send(BLEEDING))) is None
    assert "sin evidencia suficiente (mejor similitud 0.42)" in caplog.text


def test_a_draft_that_is_not_verified_is_not_sent() -> None:
    guided, _, _ = guide(
        selecting(agent_json("Toma manzanilla todos los días."), "responde", "E1.1")
    )

    assert guided is None


def test_a_model_failure_is_never_shown_to_the_person() -> None:
    selector_fails = selecting(agent_json(USEFUL), "responde", "E1.1")
    selector_fails = selector_fails | {"selection": LanguageModelError("sin modelo")}
    writer_fails = selecting(agent_json(LanguageModelError("sin modelo")), "responde", "E1.1")

    assert guide(selector_fails)[0] is None
    assert guide(writer_fails)[0] is None


# --- Consola -------------------------------------------------------------------------------------


def test_the_console_shows_the_notice_first_and_then_the_guidance() -> None:
    agent = ScriptedAgent()
    agent.current = selecting(agent_json(USEFUL), "responde", "E1.1")
    service = service_for(agent, InMemoryThreadRepository())
    pending = iter([BLEEDING])
    output: list[str] = []

    def read(_prompt: str) -> str:
        try:
            return next(pending)
        except StopIteration:
            raise EOFError from None

    ConsoleChat(service, read=read, write=output.append).run()

    answers = [line for line in output if line.startswith(ASSISTANT_LABEL)]
    assert URGENT_MESSAGE in answers[0]
    assert USEFUL in answers[1]
