"""Pruebas de la cola de un trabajador y del temporizador (ADR 0014)."""

import threading

from cardio_materno.adapters.inbound.whatsapp.dispatcher import (
    MessageDispatcher,
    ThreadingDelayedActions,
)
from cardio_materno.application.incoming_message import IncomingMessage, MessageKind
from cardio_materno.domain.user import Channel


def incoming(message_id: str) -> IncomingMessage:
    return IncomingMessage(Channel.WHATSAPP, message_id, "h", "a", MessageKind.TEXT, "text", "x")


def test_messages_are_processed_in_order_and_errors_do_not_stop_the_worker() -> None:
    processed: list[str] = []

    def handler(message: IncomingMessage) -> None:
        if message.channel_message_id == "falla":
            raise RuntimeError("error de prueba")
        processed.append(message.channel_message_id)

    dispatcher = MessageDispatcher(handler)
    dispatcher.start()
    for message_id in ("1", "falla", "2", "3"):
        assert dispatcher.submit(incoming(message_id))
    dispatcher.drain()
    dispatcher.stop()

    assert processed == ["1", "2", "3"]


def test_full_queue_rejects_new_messages() -> None:
    dispatcher = MessageDispatcher(lambda message: None, max_pending=1)

    assert dispatcher.submit(incoming("1")) is True
    assert dispatcher.submit(incoming("2")) is False


def test_delayed_action_runs_unless_cancelled() -> None:
    ran = threading.Event()
    cancelled = threading.Event()
    delayed = ThreadingDelayedActions()

    delayed.schedule(0.01, ran.set)
    cancel = delayed.schedule(5.0, cancelled.set)
    cancel()

    assert ran.wait(2.0)
    assert not cancelled.is_set()
