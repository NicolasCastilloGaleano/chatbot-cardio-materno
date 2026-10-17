"""Arranque de la interfaz web local y sus dependencias."""

import os
import sys

import uvicorn
from fastapi import FastAPI

from cardio_materno.adapters.inbound.api.web_app import create_app
from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError, load_entries
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    STARTUP_ERRORS,
    build_service,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    ConfigurationError,
    load_conversation_settings,
    load_rag_settings,
    load_web_settings,
)


def create_web_app() -> FastAPI:
    """Construye FastAPI con el servicio, repositorio y base de conocimiento.

    Raises:
        ConfigurationError: Si la configuración o la base de conocimiento no son válidas.

    Returns:
        Aplicación FastAPI con una sesión y su historial local.
    """
    settings = load_conversation_settings(os.environ, PROJECT_ROOT)
    rag_settings = load_rag_settings(os.environ, PROJECT_ROOT)
    repository = JsonFileThreadRepository(settings.threads_dir)
    service = build_service(settings, repository)
    try:
        entries = load_entries(rag_settings.entries_file)
    except KnowledgeBaseError:
        entries = []
    return create_app(service, repository, entries)


def main() -> int:
    """Carga la configuración y sirve la interfaz solo en la propia máquina (loopback).

    Returns:
        Código de salida del proceso.
    """
    use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        web = load_web_settings(os.environ)
        app = create_web_app()
    except (*STARTUP_ERRORS, ConfigurationError) as error:
        print(f"No se pudo iniciar la interfaz web: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Interfaz local disponible en http://{web.host}:{web.port}")
    uvicorn.run(app, host=web.host, port=web.port)
    return EXIT_OK
