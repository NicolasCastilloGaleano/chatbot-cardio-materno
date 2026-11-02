"""Pruebas del selector de evidencia en modo observar (HU-13, ADR 0019, paso 1.1)."""

from dataclasses import replace
from typing import Any

import pytest
from scripts.export_traces import selection_lines

from cardio_materno.adapters.inbound.api.serializers import selection_to_dict
from cardio_materno.adapters.inbound.console.debug_lines import format_selection_debug
from cardio_materno.adapters.outbound.persistence.trace_codec import (
    trace_from_dict,
    trace_to_dict,
)
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.alarm_policy import URGENT_ACCOMPANIMENT_CONTEXT
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence_selection import (
    EvidenceSelector,
    SelectionActivation,
    format_selection_context,
    notice_review,
    number_sentences,
    parse_selection,
    selection_schema,
    with_context,
)
from cardio_materno.application.stage_timer import StageTimer
from cardio_materno.application.turn_context import TurnInput
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.grounding import continues_previous
from cardio_materno.domain.knowledge import EvidenceItem, Focus, KnowledgeEntry
from cardio_materno.domain.trace import (
    OfferedSentence,
    ReplyTrace,
    SelectionTrace,
    SelectionVerdict,
)
from tests.unit.fakes import (
    BackingRetriever,
    FakeRetriever,
    ScriptedAgent,
    agent_json,
    evidence_result,
    knowledge_entry,
    make_alarm_policy,
    make_service,
    selecting,
)

REFLUX = "El reflujo causa ardor. ¿Te pasa al acostarte? Evita las comidas pesadas."
CHEST = "Eso no es normal. Busca atención de urgencias inmediatamente."
OBSERVE: dict[str, Any] = {
    "selection_activation": SelectionActivation.OBSERVE,
    "selection_prompt": "SELECTOR",
}


def item(label: str, answer: str, focus: Focus = Focus.SOLVE) -> EvidenceItem:
    entry = KnowledgeEntry(label, Domain.MATERNAL_CHILD, "Categoría", focus, "¿Trata?", answer)
    return EvidenceItem(label, entry, 0.8)


def offered(*pairs: tuple[str, str]) -> tuple[OfferedSentence, ...]:
    return tuple(OfferedSentence(sentence_id, text) for sentence_id, text in pairs)


# --- Numeración y contexto -----------------------------------------------------------------------


def test_sentences_are_numbered_without_questions_and_only_from_solve_entries() -> None:
    items = [item("E1", REFLUX), item("E2", "Pregunta dónde duele.", Focus.INQUIRE)]

    assert number_sentences(items) == offered(
        ("E1.1", "El reflujo causa ardor."), ("E1.2", "Evita las comidas pesadas.")
    )


def test_context_groups_sentences_by_entry_with_what_each_is_about() -> None:
    items = [item("E1", REFLUX)]

    context = format_selection_context(items, number_sentences(items))

    assert "[E1] (Categoría) Trata de: ¿Trata?" in context
    assert "E1.2: Evita las comidas pesadas." in context
    assert "¿Te pasa al acostarte?" not in context


def test_schema_limits_the_ids_and_how_many_can_be_chosen() -> None:
    selected = selection_schema(["E1.1", "E1.2"], 5)["properties"]["selected"]

    assert selected["items"]["enum"] == ["E1.1", "E1.2"]
    assert selected["maxItems"] == 5


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("Eso no es normal.", True),
        ("En ese caso, consulta.", True),
        ("Ahí debes ir.", True),
        ("Esa presión es elevada.", True),
        ("Estos alimentos ayudan.", False),
        ("Si tiene fiebre, consulta.", False),
    ],
)
def test_continuation_markers(sentence: str, expected: bool) -> None:
    assert continues_previous(sentence) is expected


def test_a_sentence_that_continues_brings_the_previous_one_of_its_entry() -> None:
    sentences = offered(("E1.1", "Mide la presión."), ("E1.2", "Eso ayuda."), ("E2.1", "Eso no."))

    assert with_context(["E1.2"], sentences) == ("E1.1", "E1.2")
    assert with_context(["E2.1"], sentences) == ("E2.1",)  # La anterior es de otro registro.
    assert with_context(["E1.2", "E1.1"], sentences) == ("E1.1", "E1.2")


# --- Validación ----------------------------------------------------------------------------------


def test_selection_keeps_the_order_without_repeating() -> None:
    data = {"verdict": "parcial", "selected": ["E1.2", "E1.1", "E1.2"]}

    selection = parse_selection(data, ["E1.1", "E1.2"])

    assert selection.verdict is SelectionVerdict.PARTIAL
    assert selection.ids == ("E1.2", "E1.1")


@pytest.mark.parametrize(
    "data",
    [{"verdict": "responde", "selected": []}, {"verdict": "no_responde", "selected": ["E1.1"]}],
)
def test_no_ids_or_no_answer_counts_as_no_answer(data: dict[str, Any]) -> None:
    selection = parse_selection(data, ["E1.1"])

    assert selection.verdict is SelectionVerdict.NO_ANSWER and selection.ids == ()


@pytest.mark.parametrize(
    "data",
    [
        {"verdict": "quizas", "selected": ["E1.1"]},
        {"verdict": "responde", "selected": ["E9.9"]},
        {"verdict": "responde", "selected": "E1.1"},
    ],
)
def test_invalid_selection_is_a_model_error(data: dict[str, Any]) -> None:
    with pytest.raises(LanguageModelError):
        parse_selection(data, ["E1.1"])


# --- Avisos de atención (ADR 0019, punto 1) ------------------------------------------------------


def test_notice_review_separates_chosen_entries_from_the_others() -> None:
    sentences = offered(
        ("E1.1", "El reflujo causa ardor."),
        ("E1.2", "Busca atención de urgencias."),
        ("E2.1", "Llama al 123."),
    )

    assert notice_review(["E1.1"], sentences) == (("E1.2",), ("E2.1",))
    assert notice_review([], sentences) == ((), ("E1.2", "E2.1"))
    assert notice_review(["E1.2"], sentences) == ((), ("E2.1",))


# --- Conversación: observar no cambia la respuesta -----------------------------------------------


def observed_service(agent: ScriptedAgent, answer: str, **config: Any) -> Any:
    retriever = FakeRetriever(evidence_result(knowledge_entry(answer=answer)))
    return make_service(agent, config=OBSERVE | config, retriever=retriever)


def test_observing_keeps_the_reply_and_records_the_selection() -> None:
    plain = make_service(ScriptedAgent(agent_json("Evita las comidas pesadas."))).send("ardor")
    agent = ScriptedAgent(selecting(agent_json("Evita las comidas pesadas."), "responde", "E1.2"))

    result = observed_service(agent, REFLUX).send("ardor")

    assert result.reply == plain.reply
    assert result.trace is not None and result.trace.selection is not None
    assert result.trace.selection.verdict is SelectionVerdict.ANSWERS
    assert result.trace.selection.selected == ("E1.2",)
    assert result.trace.selection.applied is False
    assert [t.stage for t in result.trace.timings] == ["análisis", "RAG", "selección", "respuesta"]
    assert agent.responder.calls[0][0].content == "SELECTOR"


def test_if_the_selector_fails_the_person_does_not_notice() -> None:
    turn = selecting(agent_json("Evita las comidas pesadas."), "responde", "E1.2")
    agent = ScriptedAgent(turn | {"selection": LanguageModelError("sin modelo")})

    result = observed_service(agent, REFLUX).send("ardor")

    assert result.reply == "Evita las comidas pesadas."
    assert result.trace is not None and result.trace.selection is not None
    assert result.trace.selection.verdict is None
    assert "selección" in [t.stage for t in result.trace.timings]


def test_turned_off_there_is_no_selector_call() -> None:
    agent = ScriptedAgent(agent_json("r"))

    result = make_service(agent).send("ardor")

    assert result.trace is not None and result.trace.selection is None
    assert len(agent.responder.calls) == 1


def test_selector_does_not_run_without_a_solve_entry() -> None:
    entry = replace(knowledge_entry(answer="Pregunta dónde duele."), focus=Focus.INQUIRE)
    retriever = FakeRetriever(evidence_result(entry))
    agent = ScriptedAgent(agent_json("Pregunta dónde duele."))

    result = make_service(agent, config=OBSERVE, retriever=retriever).send("ardor")

    assert result.trace is not None and result.trace.selection is None
    assert len(agent.responder.calls) == 1


def test_selector_does_not_run_with_an_immediate_alarm() -> None:
    agent = ScriptedAgent(agent_json("r"))
    config = OBSERVE | {"alarm_policy": make_alarm_policy()}

    result = make_service(agent, config=config).send("tengo sangrado vaginal")

    assert result.trace is None or result.trace.selection is None
    assert agent.responder.calls == []


def test_conversational_turns_do_not_call_the_selector() -> None:
    turn = agent_json("Hola.") | {"scope": "conversacional"}
    agent = ScriptedAgent(turn)

    result = make_service(agent, config=OBSERVE, retriever=BackingRetriever(agent)).send("hola")

    assert result.trace is not None and result.trace.selection is None


def test_the_selector_receives_the_urgency_context_when_accompanying() -> None:
    agent = ScriptedAgent()
    agent.current = selecting(agent_json("x"), "no_responde")
    selector = EvidenceSelector(agent.responder, "SELECTOR", 5)
    analysis = AnalysisTurn(ThreadAction.CONTINUE, Domain.MATERNAL_CHILD, "resumen")
    turn = TurnInput("¿qué hago mientras llego?", urgent_reminder=True)

    trace = selector.select(analysis, turn, [item("E1", REFLUX)], StageTimer())

    assert trace is not None and trace.verdict is SelectionVerdict.NO_ANSWER
    contents = [message.content for message in agent.responder.calls[0]]
    assert any(URGENT_ACCOMPANIMENT_CONTEXT in content for content in contents)


# --- Traza y auditoría ---------------------------------------------------------------------------


SELECTION = SelectionTrace(
    offered=offered(
        ("E1.1", "Texto uno."), ("E1.2", "Busca urgencias."), ("E2.1", "Llama al 123.")
    ),
    verdict=SelectionVerdict.PARTIAL,
    selected=("E1.1",),
    added_notices=("E1.2",),
    omitted_notices=("E2.1",),
)


def test_selection_survives_the_trace_codec_and_old_traces_have_none() -> None:
    trace = ReplyTrace(selection=SELECTION)

    assert trace_from_dict(trace_to_dict(trace)) == trace
    assert trace_from_dict({}).selection is None


def test_selection_is_shown_in_the_panel_the_console_and_the_export() -> None:
    assert selection_to_dict(SELECTION)["omitted_notices"] == ["E2.1"]
    assert "parcial" in format_selection_debug(SELECTION)
    assert "falló" in format_selection_debug(SelectionTrace(offered=()))
    lines = selection_lines(SELECTION)
    assert "elegida E1.1: Texto uno." in lines
    assert "aviso que agregaría E1.2: Busca urgencias." in lines
    assert "aviso por fuera E2.1: Llama al 123." in lines
