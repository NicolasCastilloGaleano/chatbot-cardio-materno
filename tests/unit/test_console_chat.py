"""Pruebas del chat de consola con entrada y salida simuladas."""

from cardio_materno.adapters.inbound.console.console_chat import (
    GOODBYE_TEXT,
    WELCOME_TEXT,
    ConsoleChat,
)
from cardio_materno.application.conversation_service import (
    ConversationConfig,
    ConversationService,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.conversation import ThreadStatus
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeClock,
    InMemoryThreadRepository,
    ScriptedLanguageModel,
    SequentialIds,
    agent_json,
    make_alarm_policy,
)


def run_console(
    inputs: list[str],
    model: ScriptedLanguageModel,
    repo: InMemoryThreadRepository | None = None,
    show_thread_debug: bool = False,
) -> list[str]:
    """Ejecuta la consola con las entradas dadas y devuelve todo lo mostrado."""
    pending = iter(inputs)
    output: list[str] = []

    def read(_prompt: str) -> str:
        try:
            return next(pending)
        except StopIteration:
            raise EOFError from None

    service = ConversationService(
        model,
        repo or InMemoryThreadRepository(),
        ConversationConfig(
            "sys", alarm_policy=make_alarm_policy(), clock=FakeClock(), new_id=SequentialIds()
        ),
    )
    ConsoleChat(service, show_thread_debug, read=read, write=output.append).run()
    return output


def test_shows_answer_and_exits_with_salir() -> None:
    output = run_console(["hola", "salir", "no se lee"], ScriptedLanguageModel(agent_json("eco")))

    assert output[0] == WELCOME_TEXT
    assert "Asistente: eco" in output
    assert output[-1] == GOODBYE_TEXT
    assert not any("no se lee" in line for line in output)


def test_empty_lines_are_ignored() -> None:
    output = run_console(["   ", "hola", "SALIR"], ScriptedLanguageModel(agent_json("eco")))

    assert sum(line.startswith("Asistente:") for line in output) == 1


def test_model_error_is_shown_and_chat_continues() -> None:
    model = ScriptedLanguageModel(LanguageModelError("Ollama tardó demasiado"), agent_json("eco"))

    output = run_console(["falla", "hola", "salir"], model)

    assert any("Ollama tardó demasiado" in line for line in output)
    assert "Asistente: eco" in output


def test_end_of_input_closes_gracefully() -> None:
    output = run_console(["hola"], ScriptedLanguageModel(agent_json()))

    assert output[-1] == GOODBYE_TEXT


def test_thread_debug_line_shows_thread_state_when_enabled() -> None:
    model = ScriptedLanguageModel(
        agent_json(domain="materno_infantil"),
        agent_json(),
        agent_json(thread_action="nuevo", domain="cardiovascular"),
    )

    output = run_console(["a", "b", "c", "salir"], model, show_thread_debug=True)

    debug = [line for line in output if line.startswith("[hilo")]
    assert debug == [
        "[hilo hilo-1 | materno_infantil | abierto | nuevo]",
        "[hilo hilo-1 | materno_infantil | abierto | continúa]",
        "[hilo hilo-2 | cardiovascular | abierto | nuevo]",
    ]


def test_thread_debug_line_hidden_by_default() -> None:
    output = run_console(["hola", "salir"], ScriptedLanguageModel(agent_json()))

    assert not any(line.startswith("[hilo") for line in output)


def test_exit_closes_active_thread() -> None:
    repo = InMemoryThreadRepository()

    run_console(["hola", "salir"], ScriptedLanguageModel(agent_json()), repo)

    assert repo.threads["hilo-1"].status is ThreadStatus.CLOSED


def test_alarm_is_shown_with_alert_in_debug_line() -> None:
    output = run_console(
        ["tengo sangrado vaginal", "salir"], ScriptedLanguageModel(), show_thread_debug=True
    )

    assert f"Asistente: {URGENT_MESSAGE}" in output
    assert (
        "[hilo hilo-1 | materno_infantil | abierto | nuevo"
        " | ⚠️ T-URG urgencia_inmediata (usuario)]" in output
    )


def test_debug_shows_symptoms_reported_by_agent() -> None:
    model = ScriptedLanguageModel(agent_json(reported_symptoms=["fiebre", "tos"]), agent_json())

    output = run_console(["a", "b", "salir"], model, show_thread_debug=True)

    assert "[síntomas reportados por el agente: fiebre; tos]" in output
    assert "[síntomas reportados por el agente: ninguno]" in output


def test_debug_says_agent_was_not_consulted_on_urgency() -> None:
    output = run_console(
        ["tengo sangrado vaginal", "salir"], ScriptedLanguageModel(), show_thread_debug=True
    )

    assert "[agente no consultado: urgencia detectada en el mensaje]" in output
