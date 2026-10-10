"""Punto de entrada: arma las dependencias y arranca el chat por consola."""

import os
import sys
from pathlib import Path

from cardio_materno.adapters.inbound.console.console_chat import ConsoleChat
from cardio_materno.adapters.outbound.llm.ollama_language_model import (
    OllamaLanguageModel,
    OllamaSettings,
)
from cardio_materno.application.chat_service import ChatService
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.settings import ConfigurationError, load_ollama_settings

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
SYSTEM_PROMPT_FILE = PACKAGE_DIR / "prompts" / "system_prompt_v1.md"
EXIT_OK = 0
EXIT_ERROR = 1


def main() -> int:
    """Configura y ejecuta el chat por consola.

    Returns:
        Código de salida del proceso (0 si terminó bien, 1 si hubo un error de arranque).
    """
    _use_utf8_streams()
    try:
        settings = _load_settings()
        language_model = _connect_language_model(settings)
    except (ConfigurationError, LanguageModelError) as error:
        print(f"No se pudo iniciar el asistente: {error}", file=sys.stderr)
        return EXIT_ERROR
    chat_service = ChatService(language_model, _read_system_prompt())
    ConsoleChat(chat_service).run()
    return EXIT_OK


def _use_utf8_streams() -> None:
    """Fuerza UTF-8 en la entrada y la salida (Windows usa cp1252 por defecto)."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _load_settings() -> OllamaSettings:
    """Carga `.env` (si existe) y lee la configuración de Ollama."""
    load_env_file(ENV_FILE)
    return load_ollama_settings(os.environ)


def _connect_language_model(settings: OllamaSettings) -> OllamaLanguageModel:
    """Crea el adaptador de Ollama y verifica que el servidor y el modelo estén listos."""
    print(f"Conectando con Ollama en {settings.base_url} (modelo: {settings.model})…")
    language_model = OllamaLanguageModel(settings)
    language_model.verify_ready()
    return language_model


def _read_system_prompt() -> str:
    """Lee el prompt de sistema versionado."""
    return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
