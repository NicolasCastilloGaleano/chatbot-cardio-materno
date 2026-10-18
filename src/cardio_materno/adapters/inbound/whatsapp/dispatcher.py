"""Cola de un solo trabajador y temporizador del aviso de espera (ADR 0014).

El webhook responde 200 de inmediato y deja aquí los mensajes. Un único trabajador los
procesa en orden de llegada: así se respeta el orden de cada persona y se coincide con la
capacidad real de Ollama, que atiende una solicitud a la vez.
"""

import logging
import queue
import threading
from collections.abc import Callable

from cardio_materno.application.incoming_message import IncomingMessage
from cardio_materno.application.ports.message_sender import CancelAction

DEFAULT_MAX_PENDING = 100
STOP_TIMEOUT_SECONDS = 5.0
WORKER_NAME = "whatsapp-worker"

logger = logging.getLogger(__name__)

Handler = Callable[[IncomingMessage], None]


class MessageDispatcher:
    """Cola en memoria con un hilo trabajador."""

    def __init__(self, handler: Handler, max_pending: int = DEFAULT_MAX_PENDING) -> None:
        """Crea la cola (sin arrancar el trabajador).

        Args:
            handler: Procesa un mensaje (el caso de uso).
            max_pending: Mensajes en espera antes de rechazar nuevos.
        """
        self._handler = handler
        self._queue: queue.Queue[IncomingMessage | None] = queue.Queue(max_pending)
        self._worker = threading.Thread(target=self._run, name=WORKER_NAME, daemon=True)

    def start(self) -> None:
        """Arranca el trabajador."""
        self._worker.start()

    def submit(self, message: IncomingMessage) -> bool:
        """Encola un mensaje sin bloquear.

        Returns:
            False si la cola está llena (el webhook pide a Meta que reintente).
        """
        try:
            self._queue.put_nowait(message)
        except queue.Full:
            return False
        return True

    def stop(self, timeout: float = STOP_TIMEOUT_SECONDS) -> None:
        """Termina el trabajador después del mensaje en curso."""
        self._queue.put(None)
        self._worker.join(timeout)

    def drain(self) -> None:
        """Espera a que se procesen todos los mensajes encolados (para pruebas)."""
        self._queue.join()

    def _run(self) -> None:
        """Bucle del trabajador: procesa hasta recibir la señal de parada."""
        while True:
            message = self._queue.get()
            try:
                if message is None:
                    return
                self._process(message)
            finally:
                self._queue.task_done()

    def _process(self, message: IncomingMessage) -> None:
        """Procesa un mensaje; un error se registra sin detener el trabajador."""
        try:
            self._handler(message)
        except Exception as error:  # el trabajador debe seguir atendiendo a los demás
            logger.error(
                "Falló el procesamiento de un mensaje de %s (%s): %s",
                message.channel,
                type(error).__name__,
                error,
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )


class ThreadingDelayedActions:
    """Programa acciones con `threading.Timer` (aviso de espera)."""

    def schedule(self, delay_seconds: float, action: Callable[[], None]) -> CancelAction:
        """Ejecuta `action` tras `delay_seconds` en otro hilo, salvo que se cancele antes.

        Returns:
            Función que cancela la acción si aún no empezó.
        """
        timer = threading.Timer(delay_seconds, action)
        timer.daemon = True
        timer.start()
        return timer.cancel
