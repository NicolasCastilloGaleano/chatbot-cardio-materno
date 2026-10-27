"""Pruebas del chat de consola con entrada y salida simuladas."""

from cardio_materno.adapters.inbound.console.console_chat import (
    GOODBYE_TEXT,
    WELCOME_TEXT,
    ConsoleChat,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ThreadStatus
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus
from tests.unit.fakes import (
    URGENT_MESSAGE,
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
)


def run_console(
    inputs: list[str],
    agent: ScriptedAgent,
    repo: InMemoryThreadRepository | None = None,
    show_thread_debug: bool = False,
    retriever: FakeRetriever | None = None,
) -> list[str]:
    """Ejecuta la consola con las entradas dadas y devuelve todo lo mostrado."""
    pending = iter(inputs)
    output: list[str] = []

    def read(_prompt: str) -> str:
        try:
            return next(pending)
        except StopIteration:
            raise EOFError from None

    service = make_service(agent, repo, {"alarm_policy": make_alarm_policy()}, retriever)
    ConsoleChat(service, show_thread_debug, read=read, write=output.append).run()
    return output


def test_shows_answer_and_exits_with_salir() -> None:
    output = run_console(["hola", "salir", "no se lee"], ScriptedAgent(agent_json("eco")))

    assert output[0] == WELCOME_TEXT
    assert "Asistente: eco" in output
    assert output[-1] == GOODBYE_TEXT
    assert not any("no se lee" in line for line in output)


def test_empty_lines_are_ignored() -> None:
    output = run_console(["   ", "hola", "SALIR"], ScriptedAgent(agent_json("eco")))

    assert sum(line.startswith("Asistente:") for line in output) == 1


def test_model_error_is_shown_and_chat_continues() -> None:
    agent = ScriptedAgent(LanguageModelError("Ollama tardó demasiado"), agent_json("eco"))

    output = run_console(["falla", "hola", "salir"], agent)

    assert any("Ollama tardó demasiado" in line for line in output)
    assert "Asistente: eco" in output


def test_end_of_input_closes_gracefully() -> None:
    output = run_console(["hola"], ScriptedAgent(agent_json()))

    assert output[-1] == GOODBYE_TEXT


def test_thread_debug_line_shows_thread_state_when_enabled() -> None:
    agent = ScriptedAgent(
        agent_json(domain="materno_infantil"),
        agent_json(),
        agent_json(thread_action="nuevo", domain="cardiovascular"),
    )

    output = run_console(["a", "b", "c", "salir"], agent, show_thread_debug=True)

    debug = [line for line in output if line.startswith("[hilo")]
    assert debug == [
        "[hilo hilo-1 | materno_infantil | abierto | nuevo]",
        "[hilo hilo-1 | materno_infantil | abierto | continúa]",
        "[hilo hilo-2 | cardiovascular | abierto | nuevo]",
    ]


def test_debug_lines_hidden_by_default() -> None:
    output = run_console(["hola", "salir"], ScriptedAgent(agent_json()))

    assert not any(line.startswith("[") for line in output)


def test_exit_closes_active_thread() -> None:
    repo = InMemoryThreadRepository()

    run_console(["hola", "salir"], ScriptedAgent(agent_json()), repo)

    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED


def test_alarm_is_shown_with_alert_and_agent_not_consulted() -> None:
    output = run_console(
        ["tengo sangrado vaginal", "salir"], ScriptedAgent(), show_thread_debug=True
    )

    assert f"Asistente: {URGENT_MESSAGE}" in output
    assert (
        "[hilo hilo-1 | materno_infantil | abierto | nuevo | ⚠️ T-URG urgencia_inmediata (usuario)]"
        in output
    )
    assert "[agente no consultado: urgencia detectada en el mensaje]" in output
    assert not any(line.startswith(("[evidencia", "[tiempos")) for line in output)


def test_debug_shows_symptoms_reported_by_agent() -> None:
    agent = ScriptedAgent(agent_json(reported_symptoms=["fiebre", "tos"]), agent_json())

    output = run_console(["a", "b", "salir"], agent, show_thread_debug=True)

    assert "[síntomas reportados por el agente: fiebre; tos]" in output
    assert "[síntomas reportados por el agente: ninguno]" in output


def test_debug_shows_evidence_citations_and_timings() -> None:
    retriever = FakeRetriever(evidence_result(knowledge_entry("k1"), knowledge_entry("k2")))

    output = run_console(
        ["¿qué como?", "salir"],
        ScriptedAgent(citing(agent_json(), "E2")),
        retriever=retriever,
        show_thread_debug=True,
    )

    assert "[evidencia: E1 0.80 Categoría | E2 0.80 Categoría | citadas: E2]" in output
    assert "[tiempos: análisis 0.5 s · RAG 0.5 s · respuesta 0.5 s]" in output


def test_debug_warns_when_evidence_was_not_cited() -> None:
    retriever = FakeRetriever(evidence_result(knowledge_entry()))

    question = [{"text": "¿Desde cuándo?", "evidence_id": "ninguna"}]
    agent = ScriptedAgent(agent_json() | {"sentences": question})

    output = run_console(["x", "salir"], agent, retriever=retriever, show_thread_debug=True)

    assert (
        "[evidencia: E1 0.80 Categoría | citadas: ninguna | ⚠️ la respuesta no citó evidencia]"
        in output
    )
    assert "[respaldo: 1/1 frases]" in output


def test_debug_shows_literal_fallback_and_abstention() -> None:
    claim = [{"text": "Toma manzanilla.", "evidence_id": "E1"}]
    literal_agent = ScriptedAgent(agent_json() | {"sentences": claim})
    with_evidence = FakeRetriever(evidence_result(knowledge_entry()))
    without_evidence = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT))

    literal = run_console(
        ["x", "salir"], literal_agent, retriever=with_evidence, show_thread_debug=True
    )
    abstention = run_console(
        ["x", "salir"],
        ScriptedAgent(agent_json()),
        retriever=without_evidence,
        show_thread_debug=True,
    )

    assert "[respaldo: 0/1 frases · texto literal del registro]" in literal
    assert "[respaldo: abstención sin LLM (sin evidencia suficiente)]" in abstention


def test_debug_explains_insufficient_or_unavailable_evidence() -> None:
    insufficient = FakeRetriever(RetrievalResult(RetrievalStatus.INSUFFICIENT, best_score=0.48))
    unavailable = FakeRetriever(RetrievalResult(RetrievalStatus.UNAVAILABLE))

    out1 = run_console(
        ["x"], ScriptedAgent(agent_json()), retriever=insufficient, show_thread_debug=True
    )
    out2 = run_console(
        ["x"], ScriptedAgent(agent_json()), retriever=unavailable, show_thread_debug=True
    )

    assert "[evidencia: insuficiente (mejor 0.48)]" in out1
    assert "[evidencia: no disponible (RAG desactivado o sin índice)]" in out2


def test_debug_says_evidence_not_searched_when_analysis_finds_urgency() -> None:
    agent = ScriptedAgent(agent_json(reported_symptoms=["sangrado vaginal"]))

    output = run_console(["me sale agüita rosada", "salir"], agent, show_thread_debug=True)

    assert "[evidencia: no se buscó (urgencia detectada en los síntomas)]" in output


def test_debug_for_out_of_scope_message() -> None:
    agent = ScriptedAgent(scoped(agent_json(), "fuera_de_alcance", "pregunta sobre deportes"))

    output = run_console(["¿qué opinas del fútbol?", "salir"], agent, show_thread_debug=True)

    assert "[fuera de alcance: pregunta sobre deportes · no se registra en el hilo]" in output
    assert not any(line.startswith("[hilo") for line in output)


def test_debug_for_conversational_message_inside_a_thread() -> None:
    agent = ScriptedAgent(agent_json("r1"), scoped(agent_json("de nada"), "conversacional"))

    output = run_console(["tengo acidez", "gracias", "salir"], agent, show_thread_debug=True)

    assert "[evidencia: no se buscó (mensaje conversacional)]" in output


def test_debug_for_conversational_message_without_thread() -> None:
    agent = ScriptedAgent(scoped(agent_json("hola"), "conversacional"))

    output = run_console(["hola", "salir"], agent, show_thread_debug=True)

    assert "[sin hilo: mensaje conversacional · no se registra]" in output
    assert not any(line.startswith("[hilo") for line in output)


def test_debug_warns_about_details_the_person_never_wrote() -> None:
    agent = ScriptedAgent(
        agent_json("r", reported_symptoms=["acidez en el embarazo de 34 semanas"])
    )

    output = run_console(["tengo acidez", "salir"], agent, show_thread_debug=True)

    assert "[⚠️ datos que la persona no escribió: acidez en el embarazo de 34 semanas]" in output


def test_debug_shows_the_search_query() -> None:
    turn = agent_json("r") | {"search_query": "presión arterial alta"}

    output = run_console(
        ["¿quién ganó? y la presión", "salir"], ScriptedAgent(turn), show_thread_debug=True
    )

    assert "[búsqueda: presión arterial alta]" in output


def test_debug_shows_marked_sign_codes_and_their_alert_origin() -> None:
    agent = ScriptedAgent(signing(agent_json(), "SANGRADO_VAGINAL"))

    output = run_console(["me sale agüita rosada", "salir"], agent, show_thread_debug=True)

    assert "[signos marcados: SANGRADO_VAGINAL]" in output
    assert any("T-URG urgencia_inmediata (agente_codigo)" in line for line in output)


def test_debug_marks_a_search_widened_to_both_domains() -> None:
    turn = citing(agent_json("respuesta") | {"search_query": "palpitaciones"}, "E1")
    retriever = FakeRetriever(
        RetrievalResult(RetrievalStatus.INSUFFICIENT),
        evidence_result(knowledge_entry(answer="respuesta")),
    )

    output = run_console(
        ["me palpita", "salir"], ScriptedAgent(turn), show_thread_debug=True, retriever=retriever
    )

    assert "[búsqueda: palpitaciones · ampliada a los dos dominios]" in output


def test_debug_shows_the_reminded_alarm_rules() -> None:
    first = signing(agent_json("r1"), "SANGRADO_VAGINAL")
    second = signing(agent_json("r2"), "SANGRADO_VAGINAL")

    output = run_console(
        ["me sale agüita rosada", "sí, desde ayer", "salir"],
        ScriptedAgent(first, second),
        show_thread_debug=True,
    )

    assert "[recordatorio de alarma ya avisada: T-URG]" in output
