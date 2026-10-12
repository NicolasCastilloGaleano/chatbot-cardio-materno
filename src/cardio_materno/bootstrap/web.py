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
    PROJECT_ROOT,
    STARTUP_ERRORS,
    _use_utf8_streams,
    build_service,
)
from cardio_materno.bootstrap.settings import (
    ConfigurationError,
    load_conversation_settings,
    load_rag_settings,
)

HOST = "127.0.0.1"
PORT = 8000
EXIT_OK = 0
EXIT_ERROR = 1


def create_web_app() -> FastAPI:
    """Construye FastAPI con el servicio, repositorio y base de conocimiento.

    Raises:
        ConfigurationError: Si la configuraciÃ³n o la base de conocimiento no son vÃ¡lidas.

    Returns:
        AplicaciÃ³n FastAPI con una sesiÃ³n y su historial local.
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
    """Carga configuraciÃ³n y sirve la interfaz exclusivamente en loopback.

    Returns:
        CÃ³digo de salida del proceso.
    """
    _use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        app = create_web_app()
    except (*STARTUP_ERRORS, ConfigurationError) as error:
        print(f"No se pudo iniciar la interfaz web: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Interfaz local disponible en http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
    return EXIT_OK
