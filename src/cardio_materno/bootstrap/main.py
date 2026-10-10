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
from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.application.conversation_service import (
    ConversationConfig,
    ConversationService,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.settings import (
    ConfigurationError,
    ConversationSettings,
    load_conversation_settings,
    load_ollama_settings,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
SYSTEM_PROMPT_FILE = PACKAGE_DIR / "prompts" / "system_prompt_v3.md"
EXIT_OK = 0
EXIT_ERROR = 1


def main() -> int:
    """Configura y ejecuta el chat por consola.

    Returns:
        Código de salida del proceso (0 si terminó bien, 1 si hubo un error de arranque).
    """
    _use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        conversation_settings = load_conversation_settings(os.environ, PROJECT_ROOT)
        alarm_policy = _load_alarm_policy(conversation_settings)
        language_model = _connect_language_model(load_ollama_settings(os.environ))
    except (ConfigurationError, AlarmCatalogError, LanguageModelError) as error:
        print(f"No se pudo iniciar el asistente: {error}", file=sys.stderr)
        return EXIT_ERROR
    service = _build_service(language_model, conversation_settings, alarm_policy)
    ConsoleChat(service, conversation_settings.show_thread_debug).run()
    return EXIT_OK


def _use_utf8_streams() -> None:
    """Fuerza UTF-8 en la entrada y la salida (Windows usa cp1252 por defecto)."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _connect_language_model(settings: OllamaSettings) -> OllamaLanguageModel:
    """Crea el adaptador de Ollama y verifica que el servidor y el modelo estén listos."""
    print(f"Conectando con Ollama en {settings.base_url} (modelo: {settings.model})…")
    language_model = OllamaLanguageModel(settings)
    language_model.verify_ready()
    return language_model


def _load_alarm_policy(settings: ConversationSettings) -> AlarmPolicy:
    """Carga y valida el catálogo de alarmas; informa cuántas reglas quedaron activas."""
    alarm_policy = load_alarm_policy(settings.alarm_rules_file)
    print(
        f"Reglas de alarma cargadas: {len(alarm_policy.rules)} ({settings.alarm_rules_file.name})"
    )
    return alarm_policy


def _build_service(
    language_model: OllamaLanguageModel,
    settings: ConversationSettings,
    alarm_policy: AlarmPolicy,
) -> ConversationService:
    """Arma el caso de uso con el repositorio de hilos en archivos JSON y las alarmas."""
    return ConversationService(
        language_model,
        JsonFileThreadRepository(settings.threads_dir),
        ConversationConfig(_read_system_prompt(), settings.context_messages, alarm_policy),
    )


def _read_system_prompt() -> str:
    """Lee el prompt de sistema versionado."""
    return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
