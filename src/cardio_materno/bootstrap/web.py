"""Arranque de la interfaz web local de auditoría multicanal (ADR 0013 y 0016)."""

import os
import sys

import uvicorn
from fastapi import FastAPI

from cardio_materno.adapters.inbound.api.web_app import WebOptions, create_app
from cardio_materno.adapters.outbound.persistence.sqlite_chat_audit import SqliteChatAudit
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError, load_entries
from cardio_materno.bootstrap.console import build_direct_chat
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
    WebSettings,
    load_persistence_settings,
    load_rag_settings,
    load_web_settings,
)
from cardio_materno.domain.knowledge import KnowledgeEntry


def create_web_app(web: WebSettings, database: SqliteDatabase) -> FastAPI:
    """Construye la interfaz con los chats de SQLite, el agente y la base de conocimiento.

    Args:
        web: Configuración de la interfaz.
        database: Base SQLite abierta (la misma que usan la consola y WhatsApp).

    Returns:
        Aplicación FastAPI de auditoría y chat directo.

    Raises:
        ConfigurationError: Si la configuración no es válida.
    """
    persistence = load_persistence_settings(os.environ, PROJECT_ROOT)
    return create_app(
        build_direct_chat(database, persistence),
        SqliteChatAudit(database),
        _knowledge_entries(),
        WebOptions(web.page_size, web.poll_seconds),
    )


def _knowledge_entries() -> list[KnowledgeEntry]:
    """Registros de la base para mostrar la evidencia completa (vacío si no está)."""
    try:
        return load_entries(load_rag_settings(os.environ, PROJECT_ROOT).entries_file)
    except KnowledgeBaseError:
        return []


def main() -> int:
    """Carga la configuración y sirve la interfaz solo en la propia máquina (loopback).

    Returns:
        Código de salida del proceso.
    """
    use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        web = load_web_settings(os.environ)
        persistence = load_persistence_settings(os.environ, PROJECT_ROOT)
        database = SqliteDatabase(persistence.database_path)
        app = create_web_app(web, database)
    except (*STARTUP_ERRORS, DatabaseVersionError) as error:
        print(f"No se pudo iniciar la interfaz web: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Interfaz local disponible en http://{web.host}:{web.port}")
    try:
        uvicorn.run(app, host=web.host, port=web.port)
    finally:
        database.close()
    return EXIT_OK
