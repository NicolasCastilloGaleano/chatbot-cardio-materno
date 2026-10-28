"""Composición común: modelos, alarmas, RAG y configuración del agente.

La consola arranca desde `bootstrap/console.py`, la web desde `bootstrap/web.py` y WhatsApp
desde `bootstrap/whatsapp.py`. `build_service` (servicio con hilos JSON en memoria de sesión)
queda para el benchmark y las pruebas en vivo.
"""

import os
import sys
from pathlib import Path

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
from cardio_materno.application.inquiry_policy import InquiryActivation
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.bootstrap.rag_setup import RagSetup, setup_rag
from cardio_materno.bootstrap.settings import (
    ANALYSIS_MODEL_VARIABLE,
    REPLY_MODEL_VARIABLE,
    ConfigurationError,
    ConversationSettings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
PROMPTS_DIR = PACKAGE_DIR / "prompts"
ANALYSIS_PROMPT_FILE = PROMPTS_DIR / "analysis_prompt_v7.md"
REPLY_PROMPT_FILE = PROMPTS_DIR / "reply_prompt_v4.md"
INQUIRY_ACTIVE_PENDING_NOTICE = (
    "Aviso: INQUIRY_MODE=activo aún no está implementado (HU-11, fase 3); se usa 'observar'."
)
EXIT_OK = 0
EXIT_ERROR = 1
STARTUP_ERRORS = (ConfigurationError, AlarmCatalogError, KnowledgeBaseError, LanguageModelError)


def use_utf8_streams() -> None:
    """Fuerza UTF-8 en la entrada y la salida (Windows usa cp1252 por defecto)."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def build_service(
    settings: ConversationSettings, repository: ThreadRepository | None = None
) -> ConversationService:
    """Carga alarmas, modelos y RAG, y arma el caso de uso.

    Args:
        settings: Configuración de hilos y reglas.
        repository: Repositorio opcional compartido con otro adaptador de entrada.

    Returns:
        Servicio conversacional con los puertos conectados.
    """
    ports, config = build_conversation(
        settings, repository or JsonFileThreadRepository(settings.threads_dir)
    )
    return ConversationService(ports, config)


def build_conversation(
    settings: ConversationSettings, repository: ThreadRepository
) -> tuple[ConversationPorts, ConversationConfig]:
    """Carga alarmas, modelos y RAG, y arma los puertos y la configuración del agente.

    Los canales de chat continuo (ADR 0015) crean un servicio por mensaje con estos mismos
    puertos, cambiando solo el repositorio por uno acotado al usuario.

    Args:
        settings: Configuración de hilos y reglas.
        repository: Repositorio de hilos por defecto.

    Returns:
        Puertos y configuración del servicio conversacional.
    """
    alarm_policy = _load_alarm_policy(settings)
    analyzer = _connect("análisis", load_stage_settings(os.environ, ANALYSIS_MODEL_VARIABLE))
    responder = _connect("respuesta", load_stage_settings(os.environ, REPLY_MODEL_VARIABLE))
    rag = _setup_rag()
    ports = ConversationPorts(analyzer, responder, repository, rag.retriever)
    config = ConversationConfig(
        analysis_prompt=render_system_prompt(_read(ANALYSIS_PROMPT_FILE), alarm_policy),
        reply_prompt=_read(REPLY_PROMPT_FILE),
        context_messages=settings.context_messages,
        alarm_policy=alarm_policy,
        evidence_item_chars=rag.policy.item_max_chars,
        grounding=rag.policy.grounding,
        inquiry=rag.policy.inquiry,
        inquiry_activation=_inquiry_activation(settings),
    )
    return ports, config


def _inquiry_activation(settings: ConversationSettings) -> InquiryActivation:
    """Modo de la indagación; `activo` aún no está implementado (fase 3) y se observa."""
    if settings.inquiry_activation is InquiryActivation.ACTIVE:
        print(INQUIRY_ACTIVE_PENDING_NOTICE)
        return InquiryActivation.OBSERVE
    return settings.inquiry_activation


def _connect(stage: str, settings: OllamaSettings) -> OllamaLanguageModel:
    """Crea el adaptador de una etapa, verifica el modelo y lo carga en memoria."""
    print(f"Conectando con Ollama en {settings.base_url} ({stage}: {settings.model})…")
    language_model = OllamaLanguageModel(settings)
    language_model.verify_ready()
    language_model.warm_up()
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
