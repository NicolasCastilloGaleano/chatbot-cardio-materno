"""Datos de acceso a la atención (HU-18, ADR 0023): reglas, invariancia y privacidad."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    CareAccessCatalogError,
    load_care_access_catalog,
    load_public_emergency_info,
)
from cardio_materno.adapters.outbound.persistence.trace_codec import (
    trace_from_dict,
    trace_to_dict,
)
from cardio_materno.application.agent_turn import ANALYSIS_SCHEMA, analysis_schema, parse_analysis
from cardio_materno.application.care_access import (
    ADMINISTRATIVE_HEADING,
    CARE_ACCESS_PLACEHOLDER,
    AccessTurn,
    CareAccessActivation,
    decide_care_access,
    render_care_access_prompt,
)
from cardio_materno.application.conversation_service import ConversationService, TurnResult
from cardio_materno.bootstrap.main import (
    ANALYSIS_PROMPT_FILE,
    CARE_ACCESS_ANALYSIS_PROMPT_FILE,
)
from cardio_materno.bootstrap.settings import ConfigurationError, load_conversation_settings
from cardio_materno.domain.care_access import (
    GAP_NOT_CONTROLLED,
    GAP_NOT_MEASURED,
    GAP_NOT_TREATED,
    CareAccessCatalog,
    CascadeStep,
    NoticeRoute,
    StepState,
    cascade_gap,
    cascade_state,
    contradictions,
    detect_barriers,
    follow_up_step,
)
from cardio_materno.domain.conversation import Role
from cardio_materno.domain.grounding import split_sentences
from cardio_materno.domain.trace import CareAccessTrace, ReplyTrace
from tests.unit.fakes import (
    KEEP_ACCESS_FACTS,
    URGENT_MESSAGE,
    BackingRetriever,
    FakeRetriever,
    InMemoryThreadRepository,
    ScriptedAgent,
    agent_json,
    citing,
    make_alarm_policy,
    make_service,
    scoped,
    signing,
)

REPO = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO / "knowledge" / "care_access.json"
OFF, OBSERVE, ACTIVE = (
    CareAccessActivation.OFF,
    CareAccessActivation.OBSERVE,
    CareAccessActivation.ACTIVE,
)


@pytest.fixture(scope="module")
def pending() -> CareAccessCatalog:
    """Catálogo real: todos los textos están pendientes de aprobación."""
    return load_care_access_catalog(CATALOG_FILE)


@pytest.fixture(scope="module")
def approved(tmp_path_factory: pytest.TempPathFactory) -> CareAccessCatalog:
    """Copia del catálogo real con todos los textos aprobados (solo para pruebas)."""
    text = CATALOG_FILE.read_text(encoding="utf-8").replace('"pendiente"', '"aprobado"')
    path = tmp_path_factory.mktemp("catalogo") / "care_access.json"
    path.write_text(text, encoding="utf-8")
    return load_care_access_catalog(path)


def state_of(catalog: CareAccessCatalog, *codes: str) -> dict[CascadeStep, StepState]:
    return cascade_state(codes, catalog)


# --- Cascada: solo lo declarado -----------------------------------------------------------


def test_treatment_does_not_imply_diagnosis_or_measurement(pending: CareAccessCatalog) -> None:
    state = state_of(pending, "TRATAMIENTO_COLESTEROL")

    assert state[CascadeStep.TREATED] is StepState.YES
    assert state[CascadeStep.DIAGNOSED] is StepState.UNKNOWN
    assert state[CascadeStep.MEASURED] is StepState.UNKNOWN
    assert cascade_gap(state) is None


def test_a_diagnosis_does_not_imply_a_measurement(pending: CareAccessCatalog) -> None:
    state = state_of(pending, "COLESTEROL_ALTO")

    assert state[CascadeStep.MEASURED] is StepState.UNKNOWN
    assert cascade_gap(state) is None


def test_nothing_declared_is_unknown_everywhere(pending: CareAccessCatalog) -> None:
    state = state_of(pending, "SIN_AFILIACION")

    assert set(state.values()) == {StepState.UNKNOWN}
    assert follow_up_step(state) is None and cascade_gap(state) is None


@pytest.mark.parametrize(
    ("codes", "step"),
    [
        (("COLESTEROL_MEDIDO", "COLESTEROL_NUNCA_MEDIDO"), "medicion"),
        (("COLESTEROL_ALTO", "COLESTEROL_NORMAL"), "diagnostico"),
        (("COLESTEROL_NUNCA_MEDIDO", "COLESTEROL_ALTO"), "medicion"),
        (("COLESTEROL_NUNCA_MEDIDO", "CONTROL_COLESTEROL"), "medicion"),
    ],
)
def test_opposite_statements_are_contradictory_and_give_no_notice(
    pending: CareAccessCatalog, codes: tuple[str, ...], step: str
) -> None:
    state = cascade_state(codes, pending)

    assert step in contradictions(state)
    assert cascade_gap(state) is None and follow_up_step(state) is None


@pytest.mark.parametrize(
    ("codes", "gap"),
    [
        (("COLESTEROL_NUNCA_MEDIDO",), GAP_NOT_MEASURED),
        (("COLESTEROL_ALTO", "SIN_TRATAMIENTO_COLESTEROL"), GAP_NOT_TREATED),
        (("TRATAMIENTO_COLESTEROL", "SIN_CONTROL_COLESTEROL"), GAP_NOT_CONTROLLED),
        (("SIN_TRATAMIENTO_COLESTEROL",), None),
        (("SIN_CONTROL_COLESTEROL",), None),
        (("TRATAMIENTO_COLESTEROL", "CONTROL_COLESTEROL"), None),
    ],
)
def test_a_gap_needs_every_statement_that_describes_it(
    pending: CareAccessCatalog, codes: tuple[str, ...], gap: str | None
) -> None:
    assert cascade_gap(cascade_state(codes, pending)) == gap


def test_follow_up_is_the_step_after_a_declared_yes(pending: CareAccessCatalog) -> None:
    assert follow_up_step(state_of(pending, "COLESTEROL_ALTO")) is CascadeStep.TREATED
    assert follow_up_step(state_of(pending, "TRATAMIENTO_COLESTEROL")) is CascadeStep.CONTROLLED
    assert follow_up_step(state_of(pending, "COLESTEROL_NORMAL")) is None


# --- Barreras por patrón ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("No tengo EPS desde enero", "SIN_AFILIACION"),
        ("el puesto de salud queda muy lejos", "BARRERA_DISTANCIA"),
        ("no tengo plata para el pasaje", "BARRERA_COSTO"),
        ("no me dan la cita", "BARRERA_CITA"),
        ("no me han entregado las pastillas", "BARRERA_MEDICAMENTO"),
        ("no tengo con quién dejar a los niños", "BARRERA_CUIDADO"),
    ],
)
def test_each_barrier_is_detected_in_the_persons_words(
    pending: CareAccessCatalog, text: str, code: str
) -> None:
    assert detect_barriers([text], pending) == (code,)


@pytest.mark.parametrize(
    "text", ["vivo en una vereda", "tengo EPS", "me dieron la cita", "tengo la presión alta", ""]
)
def test_a_barrier_is_never_deduced(pending: CareAccessCatalog, text: str) -> None:
    assert detect_barriers([text], pending) == ()


# --- Decisión del turno -------------------------------------------------------------------

CONSULT = NoticeRoute.CONSULTATION


def test_a_barrier_said_now_gets_its_notice(approved: CareAccessCatalog) -> None:
    decision = decide_care_access(AccessTurn("no tengo eps", route=CONSULT), approved)

    assert decision.stated_facts == ("SIN_AFILIACION",) and decision.interpreted_facts == ()
    assert decision.notice == "SIN_AFILIACION" and not decision.pending_approval


def test_a_barrier_said_earlier_does_not_trigger_again(approved: CareAccessCatalog) -> None:
    turn = AccessTurn("¿y qué más hago?", earlier_messages=("no tengo eps",), route=CONSULT)

    assert decide_care_access(turn, approved).notice == ""


def test_a_notice_already_given_is_not_repeated(approved: CareAccessCatalog) -> None:
    said = approved.notices["SIN_AFILIACION"].texts[CONSULT]
    turn = AccessTurn("sigo sin eps, no tengo eps", assistant_texts=(said,), route=CONSULT)

    assert decide_care_access(turn, approved).notice == ""


def test_without_a_route_nothing_is_added(approved: CareAccessCatalog) -> None:
    decision = decide_care_access(AccessTurn("no tengo eps"), approved)

    assert decision.notice == "" and decision.stated_facts == ("SIN_AFILIACION",)


def test_an_emergency_gets_the_urgent_variant_and_never_a_question(
    approved: CareAccessCatalog,
) -> None:
    urgent = NoticeRoute.EMERGENCY
    barrier = decide_care_access(AccessTurn("no tengo eps", route=urgent), approved)
    cascade = decide_care_access(
        AccessTurn("tengo el colesterol alto", analysis_facts=("COLESTEROL_ALTO",), route=urgent),
        approved,
    )

    assert barrier.notice == "SIN_AFILIACION" and barrier.route == "urgencias"
    assert cascade.notice == "" and cascade.question == ""


def test_what_the_model_marks_is_an_interpretation_not_a_quote(
    approved: CareAccessCatalog,
) -> None:
    turn = AccessTurn(
        "tengo la eps por el sisbén", analysis_facts=("AFILIACION_SUBSIDIADO",), route=CONSULT
    )

    decision = decide_care_access(turn, approved)

    assert decision.stated_facts == ()
    assert decision.interpreted_facts == ("AFILIACION_SUBSIDIADO",)


def test_a_cascade_code_without_any_mention_of_cholesterol_is_dropped(
    approved: CareAccessCatalog,
) -> None:
    turn = AccessTurn("me duele la cabeza", analysis_facts=("COLESTEROL_ALTO",), route=CONSULT)

    assert decide_care_access(turn, approved).facts == ()


def test_the_cascade_is_a_single_follow_up_not_a_questionnaire(
    approved: CareAccessCatalog,
) -> None:
    first = AccessTurn(
        "me salió el colesterol alto", analysis_facts=("COLESTEROL_ALTO",), route=CONSULT
    )
    asked = decide_care_access(first, approved)
    question = approved.questions[CascadeStep.TREATED].text
    later = replace(
        first,
        message="tomo pastillas para el colesterol",
        analysis_facts=("COLESTEROL_ALTO", "TRATAMIENTO_COLESTEROL"),
        assistant_texts=(question,),
    )

    assert asked.question == "tratamiento" and asked.notice == ""
    assert decide_care_access(later, approved).question == ""


@pytest.mark.parametrize(
    "change",
    [
        {"informational": True},
        {"has_question": True},
        {"message": "¿y qué más hago?"},
        {"analysis_facts": ()},
    ],
)
def test_no_question_when_it_would_not_answer_the_person(
    approved: CareAccessCatalog, change: dict[str, Any]
) -> None:
    base = AccessTurn(
        "me salió el colesterol alto", analysis_facts=("COLESTEROL_ALTO",), route=CONSULT
    )

    assert decide_care_access(replace(base, **change), approved).question == ""


def test_the_gap_notice_needs_cholesterol_in_this_message(approved: CareAccessCatalog) -> None:
    facts = ("COLESTEROL_NUNCA_MEDIDO",)
    on_topic = AccessTurn("nunca me han medido el colesterol", analysis_facts=facts, route=CONSULT)
    off_topic = AccessTurn(
        "me duele la rodilla",
        earlier_messages=("nunca me han medido el colesterol",),
        analysis_facts=facts,
        route=CONSULT,
    )

    assert decide_care_access(on_topic, approved).notice == GAP_NOT_MEASURED
    assert decide_care_access(off_topic, approved).notice == ""


# --- Catálogo y prompt --------------------------------------------------------------------


def test_real_catalog_is_valid_and_everything_is_pending(pending: CareAccessCatalog) -> None:
    assert len(pending.codes) == 17 and pending.research_text
    assert not any(notice.approved for notice in pending.notices.values())
    assert not any(question.approved for question in pending.questions.values())
    assert all(notice.basis for notice in pending.notices.values())
    assert CascadeStep.MEASURED not in pending.questions


def test_public_emergency_info_has_no_individual_content() -> None:
    info = load_public_emergency_info(REPO / "knowledge" / "public_info.json")

    assert info.phone == "123" and info.status == "PROVISIONAL"
    assert any("123" in line for line in info.lines)
    assert not any("EPS" in line for line in info.lines)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"status": "pendiente"', '"status": "listo"'),
        ('"code": "SIN_AFILIACION"', '"code": "sin afiliacion"'),
        ('"group": "afiliacion"', '"group": "otro"'),
        ('"¿Qué te dijeron del resultado de ese examen?"', '"Cuéntame del resultado."'),
    ],
)
def test_a_broken_catalog_stops_the_start(tmp_path: Path, old: str, new: str) -> None:
    text = CATALOG_FILE.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "care_access.json"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(CareAccessCatalogError):
        load_care_access_catalog(path)


def test_prompt_v9_is_v8_plus_the_access_field(pending: CareAccessCatalog) -> None:
    v8 = ANALYSIS_PROMPT_FILE.read_text(encoding="utf-8")
    v9 = CARE_ACCESS_ANALYSIS_PROMPT_FILE.read_text(encoding="utf-8")
    rendered = render_care_access_prompt(v9, pending)

    assert CARE_ACCESS_PLACEHOLDER in v9 and CARE_ACCESS_PLACEHOLDER not in rendered
    assert "- SIN_AFILIACION: Dice que no tiene EPS" in rendered
    assert all(line in v9 for line in v8.splitlines()[1:])
    assert "nada más" in v9 and CARE_ACCESS_PLACEHOLDER not in v8


def test_the_schema_is_untouched_when_the_rule_is_off() -> None:
    assert analysis_schema(()) == ANALYSIS_SCHEMA
    assert "access_facts" not in ANALYSIS_SCHEMA["properties"]
    with_facts = analysis_schema((), ("SIN_AFILIACION",))
    assert with_facts["properties"]["access_facts"]["items"]["enum"] == ["SIN_AFILIACION"]
    assert "access_facts" in with_facts["required"]


@pytest.mark.parametrize("bad", [None, "SIN_AFILIACION", [1, None], ["INVENTADO"], {"a": 1}])
def test_malformed_access_facts_never_fail_the_turn(bad: Any) -> None:
    data = {key: value for key, value in agent_json().items() if key != "reply"}

    analysis = parse_analysis(data | {"access_facts": bad}, (), ("SIN_AFILIACION",))

    assert analysis.access_facts == ()


def test_mode_is_off_by_default_and_validated(tmp_path: Path) -> None:
    assert load_conversation_settings({}, tmp_path).care_access is OFF
    assert load_conversation_settings({"CARE_ACCESS_MODE": "observar"}, tmp_path).care_access
    with pytest.raises(ConfigurationError):
        load_conversation_settings({"CARE_ACCESS_MODE": "si"}, tmp_path)


# --- Invariancia: los datos de acceso no cambian ninguna decisión del turno -----------------

Scenario = tuple[str, str, dict[str, Any], bool]
FACTS = {"access_facts": ["SIN_AFILIACION", "COLESTEROL_ALTO", "BARRERA_CITA"]}
SCENARIOS: list[Scenario] = [
    ("urgencia del filtro 1", "tengo sangrado vaginal y no tengo eps", agent_json(), True),
    (
        "urgencia por código del filtro 2",
        "me sale algo por abajo y no tengo eps",
        signing(agent_json("x"), "SANGRADO_VAGINAL") | FACTS,
        True,
    ),
    (
        "alarma prioritaria con respuesta",
        "tengo la presión alta y no me dan la cita",
        citing(agent_json("Controla la sal. ¿Desde cuándo la tienes alta?"), "E1") | FACTS,
        True,
    ),
    (
        "respuesta con evidencia",
        "me salió el colesterol alto y no tengo eps, ¿qué hago?",
        citing(agent_json("Come más verduras y frutas."), "E1") | FACTS,
        True,
    ),
    (
        "abstención sin evidencia",
        "no me han entregado las pastillas del colesterol",
        agent_json("x") | FACTS,
        False,
    ),
    (
        "fuera de alcance",
        "¿quién ganó el partido? no tengo eps",
        scoped(agent_json("x"), "fuera_de_alcance") | FACTS,
        True,
    ),
    ("saludo", "hola, no tengo eps", scoped(agent_json("Hola"), "conversacional") | FACTS, True),
    (
        "tema nuevo",
        "otra cosa: mi papá no tiene eps",
        agent_json("Cuéntame más.", thread_action="nuevo", domain="cardiovascular") | FACTS,
        True,
    ),
]


def run(
    scenario: Scenario, mode: CareAccessActivation, catalog: CareAccessCatalog
) -> dict[str, Any]:
    _, message, turn, has_evidence = scenario
    agent = ScriptedAgent(turn)
    retriever = BackingRetriever(agent) if has_evidence else FakeRetriever()
    repository = InMemoryThreadRepository()
    config = {
        "alarm_policy": make_alarm_policy(),
        "care_access": catalog,
        "care_access_activation": mode,
    }
    result = make_service(agent, repository, config, retriever).send(message)
    trace = replace(result.trace, care_access=None) if result.trace else None
    stored = [
        (m.role, replace(m.trace, care_access=None) if m.trace else None)
        for thread in repository.list_threads()
        for m in repository.recent_messages(thread.id, 10)
    ]
    return {
        "reply": result.reply,
        "alerts": [(a.rule_ids, a.severity, a.origin) for a in result.alerts],
        "out_of_scope": result.out_of_scope,
        "thread": (result.thread.domain, result.thread.summary) if result.thread else None,
        "is_new_thread": result.is_new_thread,
        "queries": list(retriever.queries),
        "analysis_calls": len(agent.analyzer.calls),
        "reply_calls": len(agent.responder.calls),
        "trace": trace,
        "stored": stored,
        "urgent_guidance": result.urgent_guidance,
    }


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_observing_changes_nothing_but_the_access_trace(
    scenario: Scenario, approved: CareAccessCatalog
) -> None:
    assert run(scenario, OBSERVE, approved) == run(scenario, OFF, approved)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_active_only_adds_text_to_the_reply(
    scenario: Scenario, approved: CareAccessCatalog
) -> None:
    off, active = run(scenario, OFF, approved), run(scenario, ACTIVE, approved)
    original, shown = off.pop("reply"), active.pop("reply")

    assert active == off
    # El aviso puede ir antes de la pregunta final: se conserva cada frase, en su orden.
    positions = [shown.find(sentence) for sentence in split_sentences(original)]
    assert -1 not in positions and positions == sorted(positions)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_pending_texts_are_never_shown_even_in_active_mode(
    scenario: Scenario, pending: CareAccessCatalog
) -> None:
    assert run(scenario, ACTIVE, pending) == run(scenario, OFF, pending)


def test_with_the_rule_off_the_analysis_is_not_asked_for_access_facts(
    approved: CareAccessCatalog,
) -> None:
    agent = ScriptedAgent(agent_json())
    config = {"care_access": approved, "care_access_activation": OFF}

    make_service(agent, None, config).send("tengo acidez")

    assert agent.analyzer.schemas[0] == ANALYSIS_SCHEMA


# --- Lo que ve la persona -----------------------------------------------------------------


def service(
    agent: ScriptedAgent, catalog: CareAccessCatalog, **options: Any
) -> tuple[ConversationService, InMemoryThreadRepository]:
    repository = InMemoryThreadRepository()
    config = {
        "alarm_policy": make_alarm_policy(),
        "care_access": catalog,
        "care_access_activation": ACTIVE,
    } | options
    return make_service(agent, repository, config), repository


def access_of(result: TurnResult) -> CareAccessTrace:
    assert result.trace is not None and result.trace.care_access is not None
    return result.trace.care_access


def test_an_approved_notice_is_shown_once_and_keeps_the_final_question(
    approved: CareAccessCatalog,
) -> None:
    turn = citing(agent_json("Come más verduras. ¿Desde cuándo lo tienes alto?"), "E1")
    agent = ScriptedAgent(turn, citing(agent_json("Come más verduras."), "E1"))
    chat, _ = service(agent, approved)
    notice = approved.notices["SIN_AFILIACION"].texts[CONSULT]

    first = chat.send("tengo el colesterol alto y no tengo eps")
    second = chat.send("sigo sin eps: no tengo eps")

    assert f"{ADMINISTRATIVE_HEADING}\n{notice}" in first.reply
    assert first.reply.endswith("¿Desde cuándo lo tienes alto?")
    assert access_of(first).applied and access_of(first).notice == "SIN_AFILIACION"
    assert notice not in second.reply and not access_of(second).applied


def test_a_pending_notice_is_recorded_but_not_shown(pending: CareAccessCatalog) -> None:
    chat, _ = service(ScriptedAgent(citing(agent_json("Come más verduras."), "E1")), pending)

    result = chat.send("tengo el colesterol alto y no tengo eps")

    access = access_of(result)
    assert result.reply == "Come más verduras."
    assert access.notice == "SIN_AFILIACION" and access.pending_approval and not access.applied


def test_the_urgent_message_goes_first_and_is_never_replaced(
    approved: CareAccessCatalog,
) -> None:
    chat, _ = service(ScriptedAgent(), approved)

    result = chat.send("tengo sangrado vaginal y no tengo eps")

    assert result.reply.startswith(URGENT_MESSAGE)
    assert approved.notices["SIN_AFILIACION"].texts[NoticeRoute.EMERGENCY] in result.reply
    assert [alert.rule_ids for alert in result.alerts] == [("T-URG",)]


# --- Privacidad: los códigos no se guardan sin autorización ---------------------------------


def stored_access(repository: InMemoryThreadRepository) -> CareAccessTrace:
    thread = repository.list_threads()[0]
    reply = [m for m in repository.recent_messages(thread.id, 10) if m.role is Role.ASSISTANT][-1]
    assert reply.trace is not None and reply.trace.care_access is not None
    return reply.trace.care_access


@pytest.mark.parametrize("mode", [OBSERVE, ACTIVE])
def test_codes_are_not_stored_without_the_research_authorization(
    approved: CareAccessCatalog, mode: CareAccessActivation
) -> None:
    turn = citing(agent_json("Come más verduras."), "E1") | FACTS
    chat, repository = service(ScriptedAgent(turn), approved, care_access_activation=mode)

    live = access_of(chat.send("me salió el colesterol alto y no tengo eps"))
    kept = stored_access(repository)

    assert live.stated_facts == ("SIN_AFILIACION",) and "COLESTEROL_ALTO" in live.facts
    assert kept.facts == () and kept.contradictions == () and kept.facts_withheld
    # Solo queda registrado un aviso que sí se mostró: su texto ya está en la respuesta.
    assert kept.applied == live.applied
    assert kept.notice == (live.notice if live.applied else "")


def test_codes_are_stored_only_with_the_authorization(approved: CareAccessCatalog) -> None:
    turn = citing(agent_json("Come más verduras."), "E1") | FACTS
    options = {KEEP_ACCESS_FACTS: True}
    chat, repository = service(ScriptedAgent(turn), approved, **options)

    chat.send("me salió el colesterol alto y no tengo eps")

    kept = stored_access(repository)
    assert "SIN_AFILIACION" in kept.facts and not kept.facts_withheld


def test_trace_round_trip_and_unchanged_storage_when_off() -> None:
    access = CareAccessTrace(("SIN_AFILIACION",), ("COLESTEROL_ALTO",), ("medicion",), "consulta")
    trace = ReplyTrace(care_access=replace(access, notice="SIN_AFILIACION", applied=True))

    assert trace_from_dict(json.loads(json.dumps(trace_to_dict(trace)))) == trace
    assert "care_access" not in trace_to_dict(ReplyTrace())
