"""Pruebas de ConversationService: hilos, contexto acotado y registro de mensajes (HU-06)."""

import json

import pytest

from cardio_materno.application.conversation_service import (
    NO_THREAD_CONTEXT,
    ConversationService,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import Domain, Role, ThreadStatus
from tests.unit.fakes import (
    FakeClock,
    InMemoryThreadRepository,
    ScriptedLanguageModel,
    SequentialIds,
    agent_json,
)


def make_service(
    model: ScriptedLanguageModel, repo: InMemoryThreadRepository, context_messages: int = 6
) -> ConversationService:
    return ConversationService(
        model, repo, "SYS", context_messages, clock=FakeClock(), new_id=SequentialIds()
    )


def test_first_message_opens_thread_and_stores_messages_with_thread_id() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(agent_json("r1", "continuar", "materno_infantil", "acidez"))

    result = make_service(model, repo).send("tengo acidez")

    assert result.is_new_thread
    assert result.thread.id == "hilo-1"
    assert result.thread.status is ThreadStatus.OPEN
    assert result.thread.domain is Domain.MATERNAL_CHILD
    assert result.thread.summary == "acidez"
    assert [(m.role, m.content, m.thread_id) for m in repo.messages["hilo-1"]] == [
        (Role.USER, "tengo acidez", "hilo-1"),
        (Role.ASSISTANT, "r1", "hilo-1"),
    ]


def test_continue_keeps_thread_and_updates_summary() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(
        agent_json("r1", summary="acidez"), agent_json("r2", summary="acidez y dieta")
    )
    service = make_service(model, repo)

    service.send("tengo acidez")
    result = service.send("¿qué como?")

    assert not result.is_new_thread
    assert result.thread.id == "hilo-1"
    assert repo.threads["hilo-1"].summary == "acidez y dieta"
    assert len(repo.messages["hilo-1"]) == 4


def test_new_topic_closes_current_thread_and_opens_another() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(
        agent_json("r1"), agent_json("r2", "nuevo", "cardiovascular", "presión alta")
    )
    service = make_service(model, repo)

    service.send("tengo acidez")
    result = service.send("mi papá tiene la presión alta")

    assert result.is_new_thread
    assert result.thread.id == "hilo-2"
    assert result.thread.domain is Domain.CARDIOVASCULAR
    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED
    assert [m.content for m in repo.messages["hilo-2"]] == ["mi papá tiene la presión alta", "r2"]


def test_first_context_says_there_is_no_active_thread() -> None:
    model = ScriptedLanguageModel(agent_json())

    make_service(model, InMemoryThreadRepository()).send("hola")

    assert [m.content for m in model.calls[0]] == ["SYS", NO_THREAD_CONTEXT, "hola"]


def test_context_is_bounded_to_thread_json_and_last_n_messages() -> None:
    model = ScriptedLanguageModel(*(agent_json(f"r{i}", summary=f"s{i}") for i in range(1, 5)))
    service = make_service(model, InMemoryThreadRepository(), context_messages=2)

    for text in ("m1", "m2", "m3", "m4"):
        service.send(text)

    context = model.calls[3]
    thread_json = json.loads(context[1].content.split("\n", 1)[1])
    assert context[0].content == "SYS"
    assert thread_json == {
        "id": "hilo-1",
        "domain": "materno_infantil",
        "summary": "s3",
        "status": "abierto",
    }
    assert [m.content for m in context[2:]] == ["m3", "r3", "m4"]


def test_end_session_closes_active_thread_and_next_message_opens_new_one() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(agent_json("r1"), agent_json("r2"))
    service = make_service(model, repo)

    service.send("hola")
    service.end_session()
    result = service.send("otra vez")

    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED
    assert result.thread.id == "hilo-2"


def test_end_session_without_thread_does_nothing() -> None:
    repo = InMemoryThreadRepository()

    make_service(ScriptedLanguageModel(), repo).end_session()

    assert repo.threads == {}


@pytest.mark.parametrize(
    "failure",
    [LanguageModelError("caído"), agent_json(domain="otro")],
)
def test_model_failure_saves_nothing_and_keeps_thread(failure: object) -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(agent_json("r1"), failure, agent_json("r3"))  # type: ignore[arg-type]
    service = make_service(model, repo)

    service.send("m1")
    with pytest.raises(LanguageModelError):
        service.send("m2")
    result = service.send("m3")

    assert result.thread.id == "hilo-1"
    assert [m.content for m in repo.messages["hilo-1"]] == ["m1", "r1", "m3", "r3"]
