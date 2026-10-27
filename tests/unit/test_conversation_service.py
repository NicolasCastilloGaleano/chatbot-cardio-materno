"""Pruebas de ConversationService: hilos, alarmas, dos llamadas y evidencia (HU-06/03/04/02)."""

import json
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import load_alarm_policy
from cardio_materno.application.alarm_policy import (
    REMINDER_MESSAGES,
    REPLY_SEPARATOR,
    AlarmPolicy,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    LITERAL_TEMPLATE,
    UNAVAILABLE_TEXT,
)
from cardio_materno.application.scope import CONVERSATIONAL_CONTEXT, OUT_OF_SCOPE_MESSAGE
from cardio_materno.application.turn_context import NO_THREAD_CONTEXT
from cardio_materno.domain.alarms import AlarmRule, AlertOrigin, Severity, compile_pattern
from cardio_materno.domain.conversation import Domain, Role, ThreadStatus
from cardio_materno.domain.grounding import split_sentences
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus
from tests.unit.fakes import (
    PRIORITY_MESSAGE,
    URGENT_MESSAGE,
    BackingRetriever,
    FakeRetriever,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    citing,
    evidence_result,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    scoped,
    signing,
    thread_of,
)

ALARMS: dict[str, Any] = {"alarm_policy": make_alarm_policy()}
FOOD_ADVICE = "Come comidas pequeñas y frecuentes."
# Registro real de la base citado en el incidente del 2026-10-11 (tipo Indagar).
HEARTBURN_ENTRY = (
    "Describe si es ardor que sube hacia el pecho o un dolor localizado, cuánto tarda en "
    "aparecer después de comer y qué alimentos lo desencadenan. ¿Hay sabor ácido, vómitos o "
    "dificultad para alimentarte? Indica las semanas de embarazo y los productos que estás "
    "usando para aliviarlo. Estos datos ayudan a distinguir síntomas digestivos de otros "
    "dolores abdominales. Si la molestia es intensa y persistente, especialmente bajo las "
    "costillas derechas o junto con dolor de cabeza o visión alterada, necesita atención "
    "obstétrica inmediata."
)


# --- Hilos (HU-06) -------------------------------------------------------------------------


def test_first_message_opens_thread_and_stores_messages_with_thread_id() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(agent_json("r1", "continuar", "materno_infantil", "acidez"))

    result = make_service(agent, repo).send("tengo acidez")

    assert result.is_new_thread
    assert thread_of(result).id == "hilo-1"
    assert thread_of(result).status is ThreadStatus.OPEN
    assert thread_of(result).domain is Domain.MATERNAL_CHILD
    assert thread_of(result).summary == "acidez"
    assert [(m.role, m.content, m.thread_id) for m in repo.messages["hilo-1"]] == [
        (Role.USER, "tengo acidez", "hilo-1"),
        (Role.ASSISTANT, "r1", "hilo-1"),
    ]


def test_continue_keeps_thread_and_updates_summary() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        agent_json("r1", summary="acidez"), agent_json("r2", summary="acidez y dieta")
    )
    service = make_service(agent, repo)

    service.send("tengo acidez")
    result = service.send("¿qué como?")

    assert not result.is_new_thread
    assert repo.threads["hilo-1"].summary == "acidez y dieta"
    assert len(repo.messages["hilo-1"]) == 4


def test_new_topic_closes_current_thread_and_opens_another() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(agent_json("r1"), agent_json("r2", "nuevo", "cardiovascular", "presión"))
    service = make_service(agent, repo)

    service.send("tengo acidez")
    result = service.send("mi papá tiene la presión alta")

    assert thread_of(result).id == "hilo-2"
    assert thread_of(result).domain is Domain.CARDIOVASCULAR
    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED
    assert [m.content for m in repo.messages["hilo-2"]] == ["mi papá tiene la presión alta", "r2"]


def test_first_analysis_context_says_there_is_no_active_thread() -> None:
    agent = ScriptedAgent(agent_json())

    make_service(agent).send("hola")

    assert [m.content for m in agent.analyzer.calls[0]] == ["ANALYSIS", NO_THREAD_CONTEXT, "hola"]


def test_analysis_context_is_bounded_and_includes_previous_replies() -> None:
    agent = ScriptedAgent(*(agent_json(f"r{i}", summary=f"s{i}") for i in range(1, 5)))
    service = make_service(agent, config={"context_messages": 2})

    for text in ("m1", "m2", "m3", "m4"):
        service.send(text)

    context = agent.analyzer.calls[3]
    thread_json = json.loads(context[1].content.split("\n", 1)[1])
    assert thread_json == {
        "id": "hilo-1",
        "domain": "materno_infantil",
        "summary": "s3",
        "status": "abierto",
    }
    assert [m.content for m in context[2:]] == ["m3", "r3", "m4"]


def test_end_session_closes_active_thread_and_next_message_opens_new_one() -> None:
    repo = InMemoryThreadRepository()
    service = make_service(ScriptedAgent(agent_json("r1"), agent_json("r2")), repo)

    service.send("hola")
    service.end_session()
    result = service.send("otra vez")

    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED
    assert thread_of(result).id == "hilo-2"


def test_end_session_without_thread_does_nothing() -> None:
    repo = InMemoryThreadRepository()

    make_service(ScriptedAgent(), repo).end_session()

    assert repo.threads == {}


@pytest.mark.parametrize(
    "failure",
    [
        LanguageModelError("análisis caído"),
        agent_json(domain="otro"),
        agent_json(reply=LanguageModelError("respuesta caída")),
    ],
    ids=["falla-analisis", "analisis-invalido", "falla-respuesta"],
)
def test_model_failure_without_alarm_saves_nothing_and_keeps_thread(failure: Any) -> None:
    repo = InMemoryThreadRepository()
    service = make_service(ScriptedAgent(agent_json("r1"), failure, agent_json("r3")), repo)

    service.send("m1")
    with pytest.raises(LanguageModelError):
        service.send("m2")
    result = service.send("m3")

    assert thread_of(result).id == "hilo-1"
    assert [m.content for m in repo.messages["hilo-1"]] == ["m1", "r1", "m3", "r3"]


# --- Alarmas: doble filtro (HU-03/HU-04, ADR 0007) ----------------------------------------


def test_urgent_user_message_skips_agent_and_rag() -> None:
    repo = InMemoryThreadRepository()
    agent, retriever = ScriptedAgent(), FakeRetriever()

    result = make_service(agent, repo, ALARMS, retriever).send("tengo sangrado vaginal")

    assert agent.analyzer.calls == [] and agent.responder.calls == [] and retriever.queries == []
    assert result.reply == URGENT_MESSAGE
    assert thread_of(result).summary == "Alerta: Sangrado vaginal."
    assert result.trace is None
    alert = repo.alerts["hilo-1"][0]
    assert (alert.rule_ids, alert.severity, alert.origin) == (
        ("T-URG",),
        Severity.IMMEDIATE,
        AlertOrigin.USER,
    )


def test_urgent_message_inside_active_thread_stays_in_that_thread() -> None:
    repo = InMemoryThreadRepository()
    service = make_service(ScriptedAgent(agent_json("r1")), repo, ALARMS)

    service.send("estoy embarazada")
    result = service.send("ahora tengo sangrado vaginal")

    assert thread_of(result).id == "hilo-1"
    assert len(repo.alerts["hilo-1"]) == 1


def test_urgent_message_of_another_domain_opens_a_thread_of_that_domain() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(agent_json("r1", domain="cardiovascular"))
    service = make_service(agent, repo, ALARMS)

    service.send("me duele el pecho")
    result = service.send("ahora tengo sangrado vaginal")

    assert thread_of(result).id == "hilo-2" and result.is_new_thread
    assert thread_of(result).domain is Domain.MATERNAL_CHILD
    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED
    assert "hilo-1" not in repo.alerts and len(repo.alerts["hilo-2"]) == 1


def test_each_reported_symptom_is_checked_on_its_own() -> None:
    context_rule = AlarmRule(
        "T-CTX",
        Domain.MATERNAL_CHILD,
        "gestante",
        "Fiebre en el embarazo",
        Severity.IMMEDIATE,
        (compile_pattern(r"^(?=.*embarazo)(?=.*fiebre)"),),
        "urg",
        "prueba",
    )
    policy = AlarmPolicy([context_rule], {"urg": URGENT_MESSAGE})
    symptoms = ["acidez en el embarazo de 34 semanas", "fiebre en el bebé"]
    agent = ScriptedAgent(agent_json("r", "nuevo", reported_symptoms=symptoms))

    result = make_service(agent, config={"alarm_policy": policy}).send("mi bebé tiene fiebre")

    assert result.alerts == () and result.reply == "r"


def test_sign_code_marked_by_analysis_triggers_the_rule_without_rag_or_reply() -> None:
    agent = ScriptedAgent(signing(agent_json(), "SANGRADO_VAGINAL"))
    retriever = FakeRetriever()

    result = make_service(agent, config=ALARMS, retriever=retriever).send(
        "me está saliendo como agüita rosada"
    )

    assert result.reply == URGENT_MESSAGE
    assert [(a.rule_ids, a.origin) for a in result.alerts] == [(("T-URG",), AlertOrigin.AGENT_CODE)]
    assert retriever.queries == [] and agent.responder.calls == []
    schema = agent.analyzer.schemas[0]["properties"]["reported_signs"]
    assert schema["items"]["enum"] == ["SANGRADO_VAGINAL", "PRESION_ALTA"]


def test_rule_found_by_text_and_code_is_recorded_once() -> None:
    agent = ScriptedAgent(
        signing(agent_json("r", reported_symptoms=["presion alta"]), "PRESION_ALTA")
    )

    result = make_service(agent, config=ALARMS).send("mi papá anda con la tensión subida")

    assert [(a.rule_ids, a.origin) for a in result.alerts] == [(("T-PRI",), AlertOrigin.AGENT)]


def test_unknown_sign_code_is_a_model_error_and_saves_nothing() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(signing(agent_json(), "INVENTADO"))

    with pytest.raises(LanguageModelError, match="INVENTADO"):
        make_service(agent, repo, ALARMS).send("x")

    assert repo.threads == {}


SEP = REPLY_SEPARATOR
URGENT_REMINDER = REMINDER_MESSAGES[Severity.IMMEDIATE]
PRIORITY_REMINDER = REMINDER_MESSAGES[Severity.PRIORITY]


def coded_turn(reply: str, *codes: str, thread_action: str = "continuar") -> dict[str, Any]:
    return signing(agent_json(reply, thread_action), *codes)


def test_rule_already_alerted_in_the_thread_is_only_reminded() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        coded_turn("r1", "SANGRADO_VAGINAL"), coded_turn("Sigue en reposo.", "SANGRADO_VAGINAL")
    )
    service = make_service(agent, repo, ALARMS)

    first = service.send("me sale agüita rosada")
    second = service.send("sí, desde ayer")

    assert first.reply == URGENT_MESSAGE
    assert second.reply == f"{URGENT_REMINDER}{SEP}Sigue en reposo."
    assert second.alerts == () and len(repo.alerts["hilo-1"]) == 1
    assert second.trace is not None and second.trace.reminded_rules == ("T-URG",)
    assert thread_of(second).id == "hilo-1"


def test_person_describing_the_sign_again_gets_the_full_alarm() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(coded_turn("r1", "SANGRADO_VAGINAL"))
    service = make_service(agent, repo, ALARMS)

    service.send("me sale agüita rosada")
    result = service.send("sigo con sangrado vaginal")

    assert result.reply == URGENT_MESSAGE and len(repo.alerts["hilo-1"]) == 2


def test_new_rule_alarms_in_full_and_keeps_the_more_severe_reminder() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        coded_turn("r1", "SANGRADO_VAGINAL"),
        coded_turn("Controla la presión.", "SANGRADO_VAGINAL", "PRESION_ALTA"),
    )
    service = make_service(agent, repo, ALARMS)

    service.send("me sale agüita rosada")
    result = service.send("y además me subió la tensión")

    assert result.reply == (f"{URGENT_REMINDER}{SEP}{PRIORITY_MESSAGE}{SEP}Controla la presión.")
    assert [a.rule_ids for a in result.alerts] == [("T-PRI",)]


def test_reminder_precedes_the_abstention() -> None:
    agent = ScriptedAgent(coded_turn("r1", "PRESION_ALTA"), coded_turn("r2", "PRESION_ALTA"))
    service = make_service(agent, config=ALARMS, retriever=FakeRetriever())

    service.send("me subió la tensión")
    result = service.send("¿y la insulina?")

    assert result.reply == f"{PRIORITY_REMINDER}{SEP}{ABSTENTION_TEXT}"


def test_new_thread_evaluates_the_alarms_from_scratch() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        coded_turn("r1", "SANGRADO_VAGINAL"),
        coded_turn("r2", "SANGRADO_VAGINAL", thread_action="nuevo"),
    )
    service = make_service(agent, repo, ALARMS)

    service.send("me sale agüita rosada")
    result = service.send("ahora es otra cosa")

    assert result.reply == URGENT_MESSAGE and thread_of(result).id == "hilo-2"
    assert len(repo.alerts["hilo-2"]) == 1


def test_baby_fever_alarm_is_reminded_and_the_conversation_continues() -> None:
    policy = load_alarm_policy(Path(__file__).resolve().parents[2] / "knowledge/alarm_rules.json")
    code = "FIEBRE_O_HIPOTERMIA_RECIEN_NACIDO"
    agent = ScriptedAgent(coded_turn("r1", code), coded_turn("Mídele la temperatura.", code))
    service = make_service(agent, config={"alarm_policy": policy})

    first = service.send("mi bebé tiene fiebre")
    second = service.send("sí, desde ayer")

    assert [a.rule_ids for a in first.alerts] == [("RN-MI-13",)]
    assert second.reply == f"{URGENT_REMINDER}{SEP}Mídele la temperatura." and second.alerts == ()


def test_priority_user_message_shows_fixed_notice_then_agent_reply() -> None:
    agent = ScriptedAgent(agent_json("consejos", domain="cardiovascular"))

    result = make_service(agent, config=ALARMS).send("tengo la presion alta")

    assert result.reply == f"{PRIORITY_MESSAGE}\n\nconsejos"
    assert result.alerts[0].severity is Severity.PRIORITY


@pytest.mark.parametrize(
    "turn",
    [LanguageModelError("análisis caído"), agent_json(reply=LanguageModelError("respuesta caída"))],
    ids=["falla-analisis", "falla-respuesta"],
)
def test_priority_alarm_survives_agent_failure(turn: Any) -> None:
    repo = InMemoryThreadRepository()

    result = make_service(ScriptedAgent(turn), repo, ALARMS).send("tengo la presion alta")

    assert result.reply == PRIORITY_MESSAGE
    assert repo.alerts[thread_of(result).id][0].rule_ids == ("T-PRI",)


def test_urgent_symptom_from_analysis_skips_rag_and_reply() -> None:
    agent, retriever = (
        ScriptedAgent(agent_json(reported_symptoms=["sangrado vaginal"])),
        FakeRetriever(),
    )

    result = make_service(agent, config=ALARMS, retriever=retriever).send("me sale agüita rosada")

    assert result.reply == URGENT_MESSAGE
    assert result.alerts[0].origin is AlertOrigin.AGENT
    assert retriever.queries == [] and agent.responder.calls == []
    assert result.trace is not None and result.trace.retrieval_status is None


def test_agent_reported_priority_symptom_keeps_agent_reply() -> None:
    agent = ScriptedAgent(agent_json("consejos", reported_symptoms=["presion alta"]))

    result = make_service(agent, config=ALARMS).send("mi papá anda con la tensión subida")

    assert result.reply == f"{PRIORITY_MESSAGE}\n\nconsejos"
    assert result.alerts[0].origin is AlertOrigin.AGENT


def test_advice_in_reply_or_summary_does_not_trigger_alarm() -> None:
    turn = agent_json(
        reply="Si tienes sangrado vaginal acude a urgencias.",
        summary="Se explicaron signos de alarma como sangrado vaginal.",
    )

    result = make_service(ScriptedAgent(turn), config=ALARMS).send("¿qué signos de alarma hay?")

    assert result.alerts == ()


def test_rule_detected_by_both_filters_is_recorded_once_as_user() -> None:
    agent = ScriptedAgent(agent_json("consejos", reported_symptoms=["presion alta"]))

    result = make_service(agent, config=ALARMS).send("tengo la presion alta")

    assert [(a.rule_ids, a.origin) for a in result.alerts] == [(("T-PRI",), AlertOrigin.USER)]


def test_agent_can_escalate_priority_to_urgent() -> None:
    agent = ScriptedAgent(agent_json("consejos", reported_symptoms=["sangrado vaginal"]))

    result = make_service(agent, config=ALARMS).send("tengo la presion alta")

    assert result.reply == URGENT_MESSAGE
    assert [a.origin for a in result.alerts] == [AlertOrigin.USER, AlertOrigin.AGENT]


# --- Evidencia y dos llamadas (HU-02, ADR 0008) ---------------------------------------------


def test_analysis_call_never_receives_evidence() -> None:
    agent = ScriptedAgent(agent_json())
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer="TEXTO-DE-EVIDENCIA")))

    make_service(agent, retriever=retriever).send("¿qué como para la acidez?")

    analysis_text = " ".join(m.content for m in agent.analyzer.calls[0])
    reply_text = " ".join(m.content for m in agent.responder.calls[0])
    assert "TEXTO-DE-EVIDENCIA" not in analysis_text
    assert "TEXTO-DE-EVIDENCIA" in reply_text


def test_retrieval_query_uses_message_summary_symptoms_and_domain() -> None:
    agent = ScriptedAgent(
        agent_json(domain="cardiovascular", summary="papá hipertenso", reported_symptoms=["mareo"])
    )
    retriever = FakeRetriever()

    make_service(agent, retriever=retriever).send("¿qué hago?")

    query = retriever.queries[0]
    assert query.text == "¿qué hago?. papá hipertenso. mareo"
    assert query.domains == (Domain.CARDIOVASCULAR,)


def test_retrieval_uses_the_reformulated_search_query_when_present() -> None:
    turn = agent_json(domain="cardiovascular") | {"search_query": "presión arterial alta"}
    retriever = FakeRetriever()

    result = make_service(ScriptedAgent(turn), retriever=retriever).send(
        "¿quién ganó? y tengo la presión alta"
    )

    assert retriever.queries[0].text == "presión arterial alta"
    assert result.trace is not None and result.trace.search_query == "presión arterial alta"


def test_symptom_with_details_the_person_never_wrote_is_flagged_in_the_trace() -> None:
    agent = ScriptedAgent(
        agent_json("r1", reported_symptoms=["acidez en el embarazo"]),
        agent_json("r2", reported_symptoms=["acidez en el embarazo de 34 semanas"]),
    )
    service = make_service(agent)

    service.send("tengo acidez en el embarazo")
    result = service.send("¿y qué más puedo comer?")

    assert result.trace is not None
    assert result.trace.unstated_symptoms == ("acidez en el embarazo de 34 semanas",)
    assert result.trace.reported_symptoms == ("acidez en el embarazo de 34 semanas",)


def test_details_said_earlier_in_the_thread_are_not_flagged() -> None:
    agent = ScriptedAgent(
        agent_json("r1", reported_symptoms=["acidez en el embarazo de 34 semanas"]),
        agent_json("r2", reported_symptoms=["acidez en el embarazo de 34 semanas"]),
    )
    service = make_service(agent)

    service.send("tengo acidez y 34 semanas")
    result = service.send("¿y qué más puedo comer?")

    assert result.trace is not None and result.trace.unstated_symptoms == ()


def test_domain_none_searches_all_domains() -> None:
    retriever = FakeRetriever()

    make_service(ScriptedAgent(agent_json(domain="ninguno")), retriever=retriever).send("hola")

    assert [q.domains for q in retriever.queries] == [()]


def test_evidence_in_the_analysis_domain_does_not_repeat_the_search() -> None:
    retriever = FakeRetriever(evidence_result(knowledge_entry()))

    result = make_service(ScriptedAgent(agent_json("r")), retriever=retriever).send("acidez")

    assert [q.domains for q in retriever.queries] == [(Domain.MATERNAL_CHILD,)]
    assert result.trace is not None and not result.trace.domain_fallback


def test_without_evidence_in_the_analysis_domain_the_search_covers_both_domains() -> None:
    entry = knowledge_entry("cv1", Domain.CARDIOVASCULAR, answer="respuesta")
    retriever = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT), evidence_result(entry))
    agent = ScriptedAgent(citing(agent_json("respuesta"), "E1"))

    result = make_service(agent, retriever=retriever).send(
        "me palpita el corazón y estoy embarazada"
    )

    assert [q.domains for q in retriever.queries] == [(Domain.MATERNAL_CHILD,), ()]
    assert retriever.queries[0].text == retriever.queries[1].text
    assert result.reply == "respuesta"
    assert result.trace is not None and result.trace.domain_fallback
    assert [ref.entry_id for ref in result.trace.evidence] == ["cv1"]


def test_without_evidence_in_both_domains_abstains_without_flagging_the_search() -> None:
    agent = ScriptedAgent(agent_json("r"))
    retriever = FakeRetriever()

    result = make_service(agent, retriever=retriever).send("¿cuánta insulina me pongo?")

    assert len(retriever.queries) == 2 and result.reply == ABSTENTION_TEXT
    assert result.trace is not None and not result.trace.domain_fallback


def test_unavailable_retriever_does_not_repeat_the_search() -> None:
    retriever = FakeRetriever(RetrievalResult(RetrievalStatus.UNAVAILABLE))

    result = make_service(ScriptedAgent(agent_json("r")), retriever=retriever).send("acidez")

    assert len(retriever.queries) == 1 and result.reply == UNAVAILABLE_TEXT


def test_reply_schema_limits_citations_to_offered_labels_and_trace_records_them() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(citing(agent_json("Come comidas pequeñas."), "E1"))
    retriever = FakeRetriever(
        evidence_result(knowledge_entry("k1", answer=FOOD_ADVICE), knowledge_entry("k2"))
    )

    result = make_service(agent, repo, retriever=retriever).send("¿qué como?")

    schema = agent.responder.schemas[0]
    sentence = schema["properties"]["sentences"]["items"]["properties"]
    assert sentence["evidence_id"]["enum"] == ["E1", "E2", "ninguna"]
    assert result.reply == "Come comidas pequeñas."
    trace = repo.messages["hilo-1"][1].trace
    assert trace is not None and trace == result.trace
    assert [ref.entry_id for ref in trace.evidence] == ["k1", "k2"]
    assert trace.cited_evidence == ("E1",)
    assert not trace.uncited


def test_citing_unoffered_label_is_an_error_and_saves_nothing() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(citing(agent_json("r"), "E9"))

    with pytest.raises(LanguageModelError, match="E9"):
        make_service(agent, repo, retriever=FakeRetriever(evidence_result(knowledge_entry()))).send(
            "x"
        )

    assert repo.threads == {}


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (RetrievalStatus.INSUFFICIENT, ABSTENTION_TEXT),
        (RetrievalStatus.UNAVAILABLE, UNAVAILABLE_TEXT),
    ],
)
def test_without_sufficient_evidence_abstains_without_calling_the_reply_model(
    status: RetrievalStatus, text: str
) -> None:
    agent = ScriptedAgent(agent_json("el jengibre ayuda"))
    retriever = FakeRetriever(RetrievalResult(status, best_score=0.44))

    result = make_service(agent, retriever=retriever).send("¿qué como si tengo acidez?")

    assert result.reply == text and agent.responder.calls == []
    assert result.trace is not None and result.trace.retrieval_status is status
    assert result.trace.grounding is None
    assert [t.stage for t in result.trace.timings] == ["análisis", "RAG"]


def test_abstention_asks_for_more_details_and_unavailable_does_not() -> None:
    assert ABSTENTION_TEXT.rstrip().endswith("?")
    assert "?" not in UNAVAILABLE_TEXT


def test_abstention_with_priority_alarm_shows_only_the_fixed_notice() -> None:
    agent = ScriptedAgent(agent_json("consejos"))

    result = make_service(agent, config=ALARMS, retriever=FakeRetriever()).send(
        "tengo la presion alta"
    )

    assert result.reply == PRIORITY_MESSAGE and agent.responder.calls == []


def test_unsupported_cited_sentence_shows_the_pertinent_literal_sentences() -> None:
    sentences = [
        {"text": "Describe si el ardor sube hacia el pecho.", "evidence_id": "E1"},
        {"text": "Come yogur, avena, almendras y nueces.", "evidence_id": "E1"},
    ]
    agent = ScriptedAgent(agent_json() | {"sentences": sentences})
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=HEARTBURN_ENTRY)))

    result = make_service(agent, retriever=retriever).send("¿qué más puedo comer?")

    first, *_, notice = split_sentences(HEARTBURN_ENTRY)
    assert result.reply == LITERAL_TEMPLATE.format(answer=f"{first} {notice}")
    assert result.trace is not None and result.trace.grounding is not None
    assert result.trace.grounding.literal and result.trace.cited_evidence == ("E1",)
    assert result.trace.grounding.dropped == ("Come yogur, avena, almendras y nueces.",)
    assert (result.trace.grounding.literal_shown, result.trace.grounding.literal_total) == (2, 5)


def test_supported_sentences_and_a_clarifying_question_are_kept() -> None:
    sentences = [
        {"text": "Cuenta si el ardor sube hacia el pecho.", "evidence_id": "E1"},
        {"text": "Evita el café y el chocolate.", "evidence_id": "ninguna"},
        {"text": "¿Desde cuándo lo sientes?", "evidence_id": "ninguna"},
    ]
    agent = ScriptedAgent(agent_json() | {"sentences": sentences})
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=HEARTBURN_ENTRY)))

    result = make_service(agent, retriever=retriever).send("tengo acidez")

    assert result.reply == "Cuenta si el ardor sube hacia el pecho. ¿Desde cuándo lo sientes?"
    assert result.trace is not None and result.trace.grounding is not None
    assert (result.trace.grounding.supported, result.trace.grounding.total) == (2, 3)
    assert not result.trace.grounding.literal


def test_reply_with_only_uncited_claims_shows_the_literal_entry_text() -> None:
    sentences = [{"text": "Toma infusiones de manzanilla.", "evidence_id": "ninguna"}]
    agent = ScriptedAgent(agent_json() | {"sentences": sentences})
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=HEARTBURN_ENTRY)))

    result = make_service(agent, retriever=retriever).send("tengo acidez")

    assert result.reply == LITERAL_TEMPLATE.format(answer=HEARTBURN_ENTRY)


def test_sufficient_evidence_without_citation_is_flagged_as_uncited() -> None:
    question = [{"text": "¿Desde cuándo lo sientes?", "evidence_id": "ninguna"}]
    agent = ScriptedAgent(agent_json() | {"sentences": question})
    retriever = FakeRetriever(evidence_result(knowledge_entry()))

    result = make_service(agent, retriever=retriever).send("¿qué como?")

    assert result.trace is not None and result.trace.uncited


def test_trace_records_symptoms_and_stage_timings() -> None:
    agent = ScriptedAgent(agent_json("r", reported_symptoms=["acidez en el embarazo"]))

    result = make_service(agent).send("tengo acidez")

    assert result.trace is not None
    assert result.trace.reported_symptoms == ("acidez en el embarazo",)
    assert [t.stage for t in result.trace.timings] == ["análisis", "RAG", "respuesta"]
    assert all(t.seconds == 0.5 for t in result.trace.timings)


def test_user_messages_have_no_trace() -> None:
    repo = InMemoryThreadRepository()

    make_service(ScriptedAgent(agent_json("r")), repo).send("hola")

    assert repo.messages["hilo-1"][0].trace is None


# --- Alcance (HU-07, ADR 0009) ------------------------------------------------------------------


def test_out_of_scope_message_gets_fixed_reply_without_rag_reply_or_thread_changes() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(scoped(agent_json(), "fuera_de_alcance", "deportes"))
    retriever = FakeRetriever()

    result = make_service(agent, repo, retriever=retriever).send("¿qué opinas del fútbol?")

    assert result.reply == OUT_OF_SCOPE_MESSAGE
    assert result.out_of_scope and result.thread is None
    assert retriever.queries == [] and agent.responder.calls == []
    assert repo.threads == {} and repo.messages == {}
    assert result.trace is not None and result.trace.scope_reason == "deportes"


def test_out_of_scope_in_the_middle_of_a_thread_keeps_it_active() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        agent_json("r1", summary="acidez"),
        scoped(agent_json(thread_action="nuevo"), "fuera_de_alcance", "deportes"),
        agent_json("r3", summary="acidez y comida"),
    )
    service = make_service(agent, repo)

    service.send("tengo acidez")
    off_topic = service.send("¿quién ganó el partido?")
    result = service.send("¿y qué más puedo comer?")

    assert thread_of(off_topic).id == "hilo-1"
    assert thread_of(result).id == "hilo-1" and not result.is_new_thread
    assert repo.threads["hilo-1"].status is ThreadStatus.OPEN
    assert [m.content for m in repo.messages["hilo-1"]] == [
        "tengo acidez",
        "r1",
        "¿y qué más puedo comer?",
        "r3",
    ]


def test_answer_to_the_assistant_question_is_answered_in_the_same_thread() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        agent_json("¿Desde cuándo tiene fiebre?", summary="fiebre del bebé"),
        scoped(agent_json("Gracias, sigue midiendo."), "fuera_de_alcance", "sin salud"),
    )
    service = make_service(agent, repo)

    service.send("mi bebé tiene fiebre")
    result = service.send("sí, desde ayer")

    assert result.reply == "Gracias, sigue midiendo." and not result.out_of_scope
    assert thread_of(result).id == "hilo-1" and len(repo.messages["hilo-1"]) == 4
    assert result.trace is not None and result.trace.scope == "en_alcance"


def test_priority_alarm_is_never_discarded_as_out_of_scope() -> None:
    agent = ScriptedAgent(scoped(agent_json("consejos"), "fuera_de_alcance", "habla de fútbol"))
    retriever = BackingRetriever(agent)

    result = make_service(agent, config=ALARMS, retriever=retriever).send(
        "vengo del partido y tengo la presion alta"
    )

    assert result.reply == f"{PRIORITY_MESSAGE}\n\nconsejos"
    assert not result.out_of_scope and len(retriever.queries) == 1


def test_urgent_alarm_wins_over_out_of_scope() -> None:
    agent = ScriptedAgent(
        scoped(agent_json(reported_symptoms=["sangrado vaginal"]), "fuera_de_alcance")
    )

    result = make_service(agent, config=ALARMS).send("estaba en el partido y me vino agüita")

    assert result.reply == URGENT_MESSAGE and not result.out_of_scope


def test_reported_symptom_overrides_out_of_scope_decision() -> None:
    agent = ScriptedAgent(
        scoped(agent_json("r", reported_symptoms=["acidez en el embarazo"]), "fuera_de_alcance")
    )
    retriever = BackingRetriever(agent)

    result = make_service(agent, retriever=retriever).send(
        "estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas"
    )

    assert result.reply == "r" and not result.out_of_scope and len(retriever.queries) == 1


def test_conversational_message_replies_without_rag() -> None:
    greeting = agent_json("¡Hola! Soy un servicio de orientación…", domain="ninguno")
    agent = ScriptedAgent(scoped(greeting, "conversacional"))
    retriever = FakeRetriever()

    result = make_service(agent, retriever=retriever).send("hola")

    assert retriever.queries == []
    assert CONVERSATIONAL_CONTEXT in [m.content for m in agent.responder.calls[0]]
    assert agent.responder.schemas[0]["properties"]["evidence_ids"]["maxItems"] == 0
    assert result.trace is not None
    assert result.trace.scope == "conversacional" and result.trace.retrieval_status is None


def test_conversational_message_without_thread_is_not_recorded() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(scoped(agent_json("¡Hola!", "nuevo", "ninguno"), "conversacional"))

    result = make_service(agent, repo).send("hola")

    assert result.thread is None and not result.is_new_thread and not result.out_of_scope
    assert repo.threads == {} and repo.messages == {}


def test_greeting_inside_a_thread_keeps_the_thread_domain() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        agent_json("r1", domain="materno_infantil"),
        scoped(agent_json("de nada", domain="ninguno"), "conversacional"),
    )
    service = make_service(agent, repo)

    service.send("tengo acidez en el embarazo")
    result = service.send("gracias")

    assert thread_of(result).domain is Domain.MATERNAL_CHILD


def test_greeting_never_opens_a_thread_nor_changes_the_active_one() -> None:
    repo = InMemoryThreadRepository()
    agent = ScriptedAgent(
        agent_json("r1", domain="cardiovascular", summary="presión"),
        scoped(agent_json("¡Hola!", "nuevo", "ninguno", "saludo"), "conversacional"),
    )
    service = make_service(agent, repo)

    service.send("tengo la presión alta")
    result = service.send("hola")

    assert thread_of(result).id == "hilo-1" and not result.is_new_thread
    assert repo.threads["hilo-1"].status is ThreadStatus.OPEN
    assert (repo.threads["hilo-1"].domain, repo.threads["hilo-1"].summary) == (
        Domain.CARDIOVASCULAR,
        "presión",
    )
    assert [m.content for m in repo.messages["hilo-1"]][-2:] == ["hola", "¡Hola!"]


def test_real_catalog_code_catches_a_phrase_that_no_pattern_covers() -> None:
    policy = load_alarm_policy(Path(__file__).resolve().parents[2] / "knowledge/alarm_rules.json")
    phrase = "el niño no retiene ni el suero"
    agent = ScriptedAgent(signing(agent_json(), "VOMITA_TODO"))

    assert policy.evaluate([phrase], AlertOrigin.USER) is None  # el filtro 1 no la capta
    result = make_service(agent, config={"alarm_policy": policy}).send(phrase)

    assert [(a.rule_ids, a.origin) for a in result.alerts] == [
        (("RN-MI-10",), AlertOrigin.AGENT_CODE)
    ]
    assert result.reply == policy.evaluate_codes(["VOMITA_TODO"]).message  # type: ignore[union-attr]
