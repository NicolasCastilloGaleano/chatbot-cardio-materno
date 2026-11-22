"""Arranque del canal WhatsApp: webhook, cola, base SQLite y agente (HU-09, ADR 0014 y 0015)."""

import logging
import os
import sys
from datetime import timedelta
from functools import partial

import uvicorn
from fastapi import FastAPI

from cardio_materno.adapters.inbound.whatsapp.dispatcher import (
    MessageDispatcher,
    PeriodicTask,
    ThreadingDelayedActions,
)
from cardio_materno.adapters.inbound.whatsapp.payload import parse_messages
from cardio_materno.adapters.inbound.whatsapp.webhook import (
    WEBHOOK_PATH,
    WebhookSecrets,
    create_whatsapp_app,
)
from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_clinician_outbox import (
    SqliteClinicianOutbox,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.whatsapp.cloud_sender import (
    CloudApiSettings,
    WhatsAppCloudSender,
)
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
)
from cardio_materno.application.incoming_message import make_identity_hasher
from cardio_materno.application.outbox_relay import OutboxRelay
from cardio_materno.bootstrap.conversation_factory import build_user_conversations
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    STARTUP_ERRORS,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    PersistenceSettings,
    WhatsAppSettings,
    load_whatsapp_settings,
)

INTERRUPTED_ERROR = "interrumpido"
RELAY_THREAD = "reenvio-profesional"


def idle_timeout(persistence: PersistenceSettings) -> timedelta:
    """Inactividad que cierra el hilo abierto, como intervalo de tiempo."""
    return timedelta(hours=persistence.idle_timeout_hours)


def create_whatsapp_runtime(
    settings: WhatsAppSettings, database: SqliteDatabase
) -> tuple[FastAPI, MessageDispatcher, PeriodicTask]:
    """Arma el webhook, la cola y el reenvío del profesional.

    Args:
        settings: Configuración del canal.
        database: Base SQLite abierta.

    Returns:
        La aplicación del webhook, la cola y la tarea de reenvío (sin arrancar).
    """
    ports = _channel_ports(settings, database)
    relay = OutboxRelay(SqliteClinicianOutbox(database), ports.sender, ports.log)
    task = PeriodicTask(relay.run_once, settings.outbox_poll_seconds, RELAY_THREAD)
    use_case = HandleIncomingMessage(
        ports,
        ChannelConfig(wait_notice_seconds=settings.wait_notice_seconds),
        build_user_conversations(
            database, timedelta(hours=settings.persistence.idle_timeout_hours)
        ),
    )
    dispatcher = MessageDispatcher(use_case.handle, settings.max_pending)
    hasher = make_identity_hasher(settings.user_hash_secret)
    app = create_whatsapp_app(
        WebhookSecrets(settings.verify_token, settings.app_secret),
        partial(parse_messages, hasher=hasher),
        dispatcher.submit,
    )
    return app, dispatcher, task


def _channel_ports(settings: WhatsAppSettings, database: SqliteDatabase) -> ChannelPorts:
    """Puertos del canal: usuarios, registro, envío a Meta y aviso de espera."""
    sender = WhatsAppCloudSender(
        CloudApiSettings(
            settings.token,
            settings.phone_number_id,
            settings.api_version,
            settings.send_timeout_seconds,
        )
    )
    return ChannelPorts(
        SqliteUserDirectory(database),
        SqliteChannelLog(database),
        sender,
        ThreadingDelayedActions(),
        SqliteClinicianOutbox(database),
    )


def main() -> int:
    """Carga la configuración, arranca la cola y sirve el webhook en loopback.

    Returns:
        Código de salida del proceso.
    """
    use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        settings = load_whatsapp_settings(os.environ, PROJECT_ROOT)
        logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
        database = SqliteDatabase(settings.persistence.database_path)
        interrupted = SqliteChannelLog(database).fail_unfinished(INTERRUPTED_ERROR)
        interrupted += SqliteClinicianOutbox(database).fail_interrupted()
        app, dispatcher, relay = create_whatsapp_runtime(settings, database)
    except (*STARTUP_ERRORS, DatabaseVersionError) as error:
        print(f"No se pudo iniciar el canal de WhatsApp: {error}", file=sys.stderr)
        return EXIT_ERROR
    if interrupted:
        print(f"Mensajes sin terminar de la ejecución anterior (marcados fallidos): {interrupted}")
    print(f"Webhook en http://{settings.host}:{settings.port}{WEBHOOK_PATH} (publícalo con ngrok)")
    dispatcher.start()
    relay.start()
    try:
        uvicorn.run(app, host=settings.host, port=settings.port)
    finally:
        relay.stop()
        dispatcher.stop()
        database.close()
    return EXIT_OK
