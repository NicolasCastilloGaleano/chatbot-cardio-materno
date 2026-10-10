"""Pruebas de ConversationService: hilos, contexto acotado y registro de mensajes (HU-06)."""

import json

import pytest

from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.application.conversation_service import (
    NO_THREAD_CONTEXT,
    ConversationConfig,
    ConversationService,
    no_alarm_policy,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.alarms import AlertOrigin, Severity
from cardio_materno.domain.conversation import Domain, Role, ThreadStatus
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    URGENT_MESSAGE,
    FakeClock,
    InMemoryThreadRepository,
    ScriptedLanguageModel,
    SequentialIds,
    agent_json,
    make_alarm_policy,
)


def make_service(
    model: ScriptedLanguageModel,
    repo: InMemoryThreadRepository,
    context_messages: int = 6,
    policy: AlarmPolicy | None = None,
) -> ConversationService:
    return ConversationService(
        model,
        repo,
        ConversationConfig(
            "SYS",
            context_messages,
            alarm_policy=policy or no_alarm_policy(),
            clock=FakeClock(),
            new_id=SequentialIds(),
        ),
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


# --- Alarmas: doble filtro (HU-03/HU-04, ADR 0007) ---


def test_urgent_user_message_skips_agent_and_opens_alarm_thread() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel()

    result = make_service(model, repo, policy=make_alarm_policy()).send("tengo sangrado vaginal")

    assert model.calls == []
    assert result.reply == URGENT_MESSAGE
    assert result.is_new_thread
    assert result.thread.domain is Domain.MATERNAL_CHILD
    assert result.thread.summary == "Alerta: Sangrado vaginal."
    alert = repo.alerts["hilo-1"][0]
    assert (alert.rule_ids, alert.severity, alert.origin) == (
        ("T-URG",),
        Severity.IMMEDIATE,
        AlertOrigin.USER,
    )
    assert [m.content for m in repo.messages["hilo-1"]] == [
        "tengo sangrado vaginal",
        URGENT_MESSAGE,
    ]


def test_urgent_message_inside_active_thread_stays_in_that_thread() -> None:
    repo = InMemoryThreadRepository()
    service = make_service(
        ScriptedLanguageModel(agent_json("r1")), repo, policy=make_alarm_policy()
    )

    service.send("estoy embarazada")
    result = service.send("ahora tengo sangrado vaginal")

    assert result.thread.id == "hilo-1"
    assert not result.is_new_thread
    assert len(repo.alerts["hilo-1"]) == 1


def test_priority_user_message_shows_fixed_notice_then_agent_reply() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(agent_json("consejos", domain="cardiovascular"))

    result = make_service(model, repo, policy=make_alarm_policy()).send("tengo la presion alta")

    assert result.reply == f"{PRIORITY_MESSAGE}\n\nconsejos"
    assert len(model.calls) == 1
    assert result.alerts[0].severity is Severity.PRIORITY


def test_priority_alarm_survives_agent_failure() -> None:
    repo = InMemoryThreadRepository()
    model = ScriptedLanguageModel(LanguageModelError("caído"))

    result = make_service(model, repo, policy=make_alarm_policy()).send("tengo la presion alta")

    assert result.reply == PRIORITY_MESSAGE
    assert repo.alerts[result.thread.id][0].rule_ids == ("T-PRI",)


def test_agent_reported_symptom_triggers_urgent_alarm_and_discards_reply() -> None:
    repo = InMemoryThreadRepository()
    turn = agent_json("respuesta del agente", reported_symptoms=["sangrado vaginal en el embarazo"])

    result = make_service(ScriptedLanguageModel(turn), repo, policy=make_alarm_policy()).send(
        "me sale agüita rosada por abajo"
    )

    assert result.reply == URGENT_MESSAGE
    assert result.alerts[0].origin is AlertOrigin.AGENT
    assert result.alerts[0].rule_ids == ("T-URG",)


def test_agent_reported_priority_symptom_keeps_agent_reply() -> None:
    turn = agent_json("consejos", reported_symptoms=["presion alta"])

    result = make_service(
        ScriptedLanguageModel(turn), InMemoryThreadRepository(), policy=make_alarm_policy()
    ).send("mi papá anda con la tensión subida")

    assert result.reply == f"{PRIORITY_MESSAGE}\n\nconsejos"
    assert result.alerts[0].origin is AlertOrigin.AGENT


def test_advice_in_reply_or_summary_does_not_trigger_alarm() -> None:
    turn = agent_json(
        reply="Si tienes sangrado vaginal acude a urgencias.",
        summary="Se explicaron signos de alarma como sangrado vaginal.",
    )

    result = make_service(
        ScriptedLanguageModel(turn), InMemoryThreadRepository(), policy=make_alarm_policy()
    ).send("¿qué signos de alarma hay en el embarazo?")

    assert result.alerts == ()
    assert result.reply == "Si tienes sangrado vaginal acude a urgencias."


def test_rule_detected_by_both_filters_is_recorded_once_as_user() -> None:
    repo = InMemoryThreadRepository()
    turn = agent_json("consejos", reported_symptoms=["presion alta"])

    result = make_service(ScriptedLanguageModel(turn), repo, policy=make_alarm_policy()).send(
        "tengo la presion alta"
    )

    assert [(a.rule_ids, a.origin) for a in result.alerts] == [(("T-PRI",), AlertOrigin.USER)]


def test_agent_can_escalate_priority_to_urgent() -> None:
    turn = agent_json("consejos", reported_symptoms=["sangrado vaginal"])

    result = make_service(
        ScriptedLanguageModel(turn), InMemoryThreadRepository(), policy=make_alarm_policy()
    ).send("tengo la presion alta")

    assert result.reply == URGENT_MESSAGE
    assert [a.origin for a in result.alerts] == [AlertOrigin.USER, AlertOrigin.AGENT]
