"""Chat interactivo por consola (HU-00, HU-06, HU-02, HU-10)."""

from collections.abc import Callable
from typing import Protocol

from cardio_materno.adapters.inbound.console.debug_lines import debug_lines
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.errors import LanguageModelError

EXIT_COMMANDS = frozenset({"salir", "exit", "quit"})
USER_PROMPT = "\nTú: "
ASSISTANT_LABEL = "Asistente: "
THINKING_TEXT = "(pensando…)"
ERROR_PREFIX = "⚠️  "
WELCOME_TEXT = (
    "=== Asistente de teleorientación cardio-materno (prototipo técnico) ===\n"
    "Escribe tu mensaje y presiona Enter. Escribe 'salir' para terminar."
)
GOODBYE_TEXT = "Hasta pronto. Cuídate mucho."

Reader = Callable[[str], str]
Writer = Callable[[str], None]


class ChatSession(Protocol):
    """Sesión que atiende la consola: un chat de consola (HU-10) o un servicio en memoria."""

    def send(self, user_text: str) -> TurnResult:
        """Procesa un mensaje y devuelve el turno."""
        ...

    def end_session(self) -> None:
        """Cierra el hilo activo al salir."""
        ...


class ConsoleChat:
    """Bucle de lectura y respuesta que conecta la consola con su sesión de chat."""

    def __init__(
        self,
        service: ChatSession,
        show_thread_debug: bool = False,
        read: Reader = input,
        write: Writer = print,
    ) -> None:
        """Crea el chat de consola.

        Args:
            service: Sesión que procesa cada mensaje.
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
            for line in debug_lines(result):
                self._write(line)
