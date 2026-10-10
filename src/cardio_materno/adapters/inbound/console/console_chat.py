"""Chat interactivo por consola (HU-00, HU-06)."""

from collections.abc import Callable

from cardio_materno.application.conversation_service import ConversationService, TurnResult
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.alarms import Alert

EXIT_COMMANDS = frozenset({"salir", "exit", "quit"})
USER_PROMPT = "\nTú: "
ASSISTANT_LABEL = "Asistente: "
THINKING_TEXT = "(pensando…)"
ERROR_PREFIX = "⚠️  "
SHORT_ID_LENGTH = 8
THREAD_DEBUG_TEMPLATE = "[hilo {id} | {domain} | {status} | {change}{alerts}]"
ALERT_DEBUG_TEMPLATE = " | ⚠️ {rule_ids} {severity} ({origin})"
NEW_THREAD_LABEL = "nuevo"
SAME_THREAD_LABEL = "continúa"
WELCOME_TEXT = (
    "=== Asistente de teleorientación cardio-materno (prototipo técnico) ===\n"
    "Escribe tu mensaje y presiona Enter. Escribe 'salir' para terminar."
)
GOODBYE_TEXT = "Hasta pronto. Cuídate mucho."

Reader = Callable[[str], str]
Writer = Callable[[str], None]


class ConsoleChat:
    """Bucle de lectura y respuesta que conecta la consola con el ConversationService."""

    def __init__(
        self,
        service: ConversationService,
        show_thread_debug: bool = False,
        read: Reader = input,
        write: Writer = print,
    ) -> None:
        """Crea el chat de consola.

        Args:
            service: Caso de uso que procesa cada mensaje.
            show_thread_debug: Si True, muestra el estado del hilo después de cada respuesta.
            read: Función que lee una línea mostrando un prompt (por defecto `input`).
            write: Función que muestra texto (por defecto `print`).
        """
        self._service = service
        self._show_thread_debug = show_thread_debug
        self._read = read
        self._write = write

    def run(self) -> None:
        """Muestra la bienvenida, conversa hasta que el usuario sale y cierra el hilo activo."""
        self._write(WELCOME_TEXT)
        while (text := self._next_message()) is not None:
            self._answer(text)
        self._service.end_session()
        self._write(GOODBYE_TEXT)

    def _next_message(self) -> str | None:
        """Lee el siguiente mensaje no vacío; devuelve None si el usuario quiere salir."""
        while True:
            try:
                text = self._read(USER_PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if text.lower() in EXIT_COMMANDS:
                return None
            if text:
                return text

    def _answer(self, text: str) -> None:
        """Obtiene la respuesta del asistente y la muestra; los errores no cierran el chat."""
        self._write(THINKING_TEXT)
        try:
            result = self._service.send(text)
        except LanguageModelError as error:
            self._write(f"{ERROR_PREFIX}{error}")
            return
        self._write(f"{ASSISTANT_LABEL}{result.reply}")
        if self._show_thread_debug:
            self._write(format_thread_debug(result))


def format_thread_debug(result: TurnResult) -> str:
    """Línea compacta con el estado del hilo.

    Ejemplo:
        "[hilo 3f2a91c0 | cardiovascular | abierto | nuevo
          | ⚠️ RN-CV-01 urgencia_inmediata (usuario)]" (en una sola línea).

    Args:
        result: Resultado del turno.

    Returns:
        Texto para mostrar en la consola.
    """
    return THREAD_DEBUG_TEMPLATE.format(
        id=result.thread.id[:SHORT_ID_LENGTH],
        domain=result.thread.domain,
        status=result.thread.status,
        change=NEW_THREAD_LABEL if result.is_new_thread else SAME_THREAD_LABEL,
        alerts="".join(format_alert_debug(alert) for alert in result.alerts),
    )


def format_alert_debug(alert: Alert) -> str:
    """Fragmento de la línea de depuración que describe una alerta."""
    return ALERT_DEBUG_TEMPLATE.format(
        rule_ids=",".join(alert.rule_ids), severity=alert.severity, origin=alert.origin
    )
