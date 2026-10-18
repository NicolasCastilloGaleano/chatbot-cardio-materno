"""Arranque del canal WhatsApp: webhook, cola, base SQLite y agente (HU-09, ADR 0014 y 0015)."""

import logging
import os
import sys
from dataclasses import replace
from datetime import timedelta
from functools import partial

import uvicorn
from fastapi import FastAPI

from cardio_materno.adapters.inbound.whatsapp.dispatcher import (
    MessageDispatcher,
    ThreadingDelayedActions,
)
from cardio_materno.adapters.inbound.whatsapp.payload import parse_messages
from cardio_materno.adapters.inbound.whatsapp.webhook import (
    WEBHOOK_PATH,
    WebhookSecrets,
    create_whatsapp_app,
)
from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_thread_repository import (
    SqliteThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.adapters.outbound.whatsapp.cloud_sender import (
    CloudApiSettings,
    WhatsAppCloudSender,
)
from cardio_materno.application.conversation_service import ConversationService
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
    ServiceFactory,
)
from cardio_materno.application.incoming_message import make_identity_hasher
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    STARTUP_ERRORS,
    build_conversation,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    WhatsAppSettings,
    load_conversation_settings,
    load_whatsapp_settings,
)

INTERRUPTED_ERROR = "interrumpido"


def create_whatsapp_runtime(
    settings: WhatsAppSettings, database: SqliteDatabase
) -> tuple[FastAPI, MessageDispatcher]:
    """Arma el webhook y la cola con el agente y la persistencia por usuario.

    Args:
        settings: Configuración del canal.
        database: Base SQLite abierta.

    Returns:
        La aplicación del webhook y la cola (sin arrancar).
    """
    use_case = HandleIncomingMessage(
        _channel_ports(settings, database),
        ChannelConfig(
            idle_timeout=timedelta(hours=settings.idle_timeout_hours),
            wait_notice_seconds=settings.wait_notice_seconds,
        ),
        _service_factory(database),
    )
    dispatcher = MessageDispatcher(use_case.handle, settings.max_pending)
    hasher = make_identity_hasher(settings.user_hash_secret)
    app = create_whatsapp_app(
        WebhookSecrets(settings.verify_token, settings.app_secret),
        partial(parse_messages, hasher=hasher),
        dispatcher.submit,
    )
    return app, dispatcher


def _service_factory(database: SqliteDatabase) -> ServiceFactory:
    """Conecta modelos y RAG una sola vez; cada mensaje usa un servicio acotado al usuario."""
    settings = load_conversation_settings(os.environ, PROJECT_ROOT)
    base_ports, config = build_conversation(settings, SqliteThreadRepository(database, None))

    def create(repository: ThreadRepository, active_thread_id: str | None) -> ConversationService:
        return ConversationService(
            replace(base_ports, repository=repository), config, active_thread_id
        )

    return create


def _channel_ports(settings: WhatsAppSettings, database: SqliteDatabase) -> ChannelPorts:
    """Puertos del canal: usuarios, hilos, registro, envío a Meta y aviso de espera."""
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
        SqliteUserThreadStore(database),
        SqliteChannelLog(database),
        sender,
        ThreadingDelayedActions(),
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
        database = SqliteDatabase(settings.database_path)
        interrupted = SqliteChannelLog(database).fail_unfinished(INTERRUPTED_ERROR)
        app, dispatcher = create_whatsapp_runtime(settings, database)
    except (*STARTUP_ERRORS, DatabaseVersionError) as error:
        print(f"No se pudo iniciar el canal de WhatsApp: {error}", file=sys.stderr)
        return EXIT_ERROR
    if interrupted:
        print(f"Mensajes sin terminar de la ejecución anterior (marcados fallidos): {interrupted}")
    print(f"Webhook en http://{settings.host}:{settings.port}{WEBHOOK_PATH} (publícalo con ngrok)")
    dispatcher.start()
    try:
        uvicorn.run(app, host=settings.host, port=settings.port)
    finally:
        dispatcher.stop()
        database.close()
    return EXIT_OK
