"""Arranque de la interfaz web local de auditoría multicanal (ADR 0013 y 0016)."""

import os
import sys

import uvicorn
from fastapi import FastAPI

from cardio_materno.adapters.inbound.api.serializers import Knowledge
from cardio_materno.adapters.inbound.api.web_app import (
    ClinicianAccess,
    WebOptions,
    WebServices,
    create_app,
)
from cardio_materno.adapters.outbound.clinical_rules.json_care_access_catalog import (
    load_public_emergency_info,
)
from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.adapters.outbound.persistence.sqlite_case_repository import SqliteCaseInbox
from cardio_materno.adapters.outbound.persistence.sqlite_chat_audit import SqliteChatAudit
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
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError, load_entries
from cardio_materno.adapters.outbound.rag.provenance_file import (
    load_provenance,
    provenance_path,
)
from cardio_materno.application.citizen_chat import CitizenChat, CitizenPolicy
from cardio_materno.application.clinician_draft import ClinicianDraftWriter
from cardio_materno.application.clinician_review import ClinicianReview
from cardio_materno.bootstrap.console import build_direct_chat
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    CLINICIAN_DRAFT_PROMPT_FILE,
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    STARTUP_ERRORS,
    load_care_access,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    REPLY_MODEL_VARIABLE,
    WebSettings,
    load_conversation_settings,
    load_persistence_settings,
    load_rag_settings,
    load_stage_settings,
    load_web_settings,
)


def create_web_app(web: WebSettings, database: SqliteDatabase) -> FastAPI:
    """Construye la interfaz con los chats de SQLite, el agente y la base de conocimiento.

    Args:
        web: Configuración de la interfaz.
        database: Base SQLite abierta (la misma que usan la consola y WhatsApp).

    Returns:
        Aplicación FastAPI con la vista ciudadana y la del equipo.

    Raises:
        ConfigurationError: Si la configuración no es válida.
    """
    persistence = load_persistence_settings(os.environ, PROJECT_ROOT)
    chats = build_direct_chat(database, persistence)
    knowledge = _knowledge()
    research_text = knowledge.care_access.research_text if knowledge.care_access else ""
    policy = CitizenPolicy(persistence.consent_required, research_text)
    citizen = CitizenChat(chats, SqliteUserDirectory(database), policy)
    audit = SqliteChatAudit(database)
    services = WebServices(chats, citizen, audit, _clinician_access(web, database))
    return create_app(services, knowledge, WebOptions(web.page_size, web.poll_seconds))


def _clinician_access(web: WebSettings, database: SqliteDatabase) -> ClinicianAccess | None:
    """Apartado del profesional (HU-16) si hay clave; el borrador usa el modelo de respuesta."""
    if not web.clinician_access_key:
        return None
    model = OllamaLanguageModel(load_stage_settings(os.environ, REPLY_MODEL_VARIABLE))
    writer = ClinicianDraftWriter(model, CLINICIAN_DRAFT_PROMPT_FILE.read_text(encoding="utf-8"))
    review = ClinicianReview(
        SqliteCaseInbox(database),
        SqliteUserThreadStore(database),
        writer,
        outbox=SqliteClinicianOutbox(database),
    )
    return ClinicianAccess(review, web.clinician_access_key)


def _knowledge() -> Knowledge:
    """Registros y procedencia para explicar la evidencia (vacío si la base no está)."""
    entries_file = load_rag_settings(os.environ, PROJECT_ROOT).entries_file
    settings = load_conversation_settings(os.environ, PROJECT_ROOT)
    access = load_care_access(settings)
    emergency = load_public_emergency_info(settings.public_info_file)
    try:
        entries = {entry.id: entry for entry in load_entries(entries_file)}
        provenance = load_provenance(provenance_path(entries_file))
    except KnowledgeBaseError:
        return Knowledge(care_access=access, emergency=emergency)
    return Knowledge(entries, provenance, access, emergency)


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
    print(f"Vista ciudadana: http://{web.host}:{web.port}/")
    print(f"Vista del equipo: http://{web.host}:{web.port}/equipo")
    try:
        uvicorn.run(app, host=web.host, port=web.port)
    finally:
        database.close()
    return EXIT_OK
