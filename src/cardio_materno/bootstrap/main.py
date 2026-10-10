"""Punto de entrada: arma las dependencias y arranca el chat por consola."""

import os
import sys
from pathlib import Path

from cardio_materno.adapters.inbound.console.console_chat import ConsoleChat
from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import (
    AlarmCatalogError,
    load_alarm_policy,
)
from cardio_materno.adapters.outbound.llm.ollama_language_model import (
    OllamaLanguageModel,
    OllamaSettings,
)
from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError
from cardio_materno.application.alarm_policy import AlarmPolicy, render_system_prompt
from cardio_materno.application.conversation_service import (
    ConversationConfig,
    ConversationPorts,
    ConversationService,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.rag_setup import RagSetup, setup_rag
from cardio_materno.bootstrap.settings import (
    ANALYSIS_MODEL_VARIABLE,
    REPLY_MODEL_VARIABLE,
    ConfigurationError,
    ConversationSettings,
    load_conversation_settings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
ANALYSIS_PROMPT_FILE = PROMPTS_DIR / "analysis_prompt_v1.md"
REPLY_PROMPT_FILE = PROMPTS_DIR / "reply_prompt_v1.md"
EXIT_OK = 0
EXIT_ERROR = 1
STARTUP_ERRORS = (ConfigurationError, AlarmCatalogError, KnowledgeBaseError, LanguageModelError)


def main() -> int:
    """Configura y ejecuta el chat por consola.

    Returns:
        Código de salida del proceso (0 si terminó bien, 1 si hubo un error de arranque).
    """
    _use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        settings = load_conversation_settings(os.environ, PROJECT_ROOT)
        service = _build_service(settings)
    except STARTUP_ERRORS as error:
        print(f"No se pudo iniciar el asistente: {error}", file=sys.stderr)
        return EXIT_ERROR
    ConsoleChat(service, settings.show_thread_debug).run()
    return EXIT_OK


def _use_utf8_streams() -> None:
    """Fuerza UTF-8 en la entrada y la salida (Windows usa cp1252 por defecto)."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _build_service(settings: ConversationSettings) -> ConversationService:
    """Carga alarmas, modelos y RAG, y arma el caso de uso."""
    alarm_policy = _load_alarm_policy(settings)
    analyzer = _connect("análisis", load_stage_settings(os.environ, ANALYSIS_MODEL_VARIABLE))
    responder = _connect("respuesta", load_stage_settings(os.environ, REPLY_MODEL_VARIABLE))
    rag = _setup_rag()
    ports = ConversationPorts(
        analyzer, responder, JsonFileThreadRepository(settings.threads_dir), rag.retriever
    )
    config = ConversationConfig(
        analysis_prompt=render_system_prompt(_read(ANALYSIS_PROMPT_FILE), alarm_policy),
        reply_prompt=_read(REPLY_PROMPT_FILE),
        context_messages=settings.context_messages,
        alarm_policy=alarm_policy,
        evidence_item_chars=rag.policy.item_max_chars,
    )
    return ConversationService(ports, config)


def _connect(stage: str, settings: OllamaSettings) -> OllamaLanguageModel:
    """Crea el adaptador de Ollama de una etapa y verifica que el modelo esté instalado."""
    print(f"Conectando con Ollama en {settings.base_url} ({stage}: {settings.model})…")
    language_model = OllamaLanguageModel(settings)
    language_model.verify_ready()
    return language_model


def _setup_rag() -> RagSetup:
    """Prepara el RAG e informa su estado (si no está disponible, el chat sigue sin él)."""
    rag = setup_rag(
        load_rag_settings(os.environ, PROJECT_ROOT), load_ollama_settings(os.environ).base_url
    )
    print(rag.status_message)
    return rag


def _load_alarm_policy(settings: ConversationSettings) -> AlarmPolicy:
    """Carga y valida el catálogo de alarmas; informa cuántas reglas quedaron activas."""
    alarm_policy = load_alarm_policy(settings.alarm_rules_file)
    print(
        f"Reglas de alarma cargadas: {len(alarm_policy.rules)} ({settings.alarm_rules_file.name})"
    )
    return alarm_policy


def _read(path: Path) -> str:
    """Lee un prompt versionado."""
    return path.read_text(encoding="utf-8").strip()
