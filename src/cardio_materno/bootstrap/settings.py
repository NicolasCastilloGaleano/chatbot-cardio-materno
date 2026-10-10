"""Lectura de la configuración desde variables de entorno."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaSettings

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "mistral-small3.1:24b"
DEFAULT_TIMEOUT_SECONDS = "180"
DEFAULT_TEMPERATURE = "0.3"
DEFAULT_NUM_CTX = "4096"
DEFAULT_THREAD_CONTEXT_MESSAGES = "6"
DEFAULT_SHOW_THREAD_DEBUG = "true"
DEFAULT_THREADS_DIR = "data/threads"
DEFAULT_ALARM_RULES_FILE = "knowledge/alarm_rules.json"
TRUE_VALUES = frozenset({"true", "1", "si", "sí", "yes"})


class ConfigurationError(Exception):
    """Una variable de configuración tiene un valor inválido."""


@dataclass(frozen=True)
class ConversationSettings:
    """Configuración de los hilos conversacionales (HU-06).

    Attributes:
        context_messages: Mensajes recientes del hilo que se envían al agente.
        show_thread_debug: Si se muestra en consola la línea con el estado del hilo.
        threads_dir: Carpeta de los archivos JSON de los hilos.
        alarm_rules_file: Catálogo de reglas de alarma (ADR 0007).
    """

    context_messages: int
    show_thread_debug: bool
    threads_dir: Path
    alarm_rules_file: Path


def load_conversation_settings(env: Mapping[str, str], project_root: Path) -> ConversationSettings:
    """Construye la configuración de los hilos a partir de las variables de entorno.

    Args:
        env: Variables de entorno (normalmente `os.environ`).
        project_root: Raíz del proyecto, para resolver rutas relativas.

    Returns:
        Configuración validada.

    Raises:
        ConfigurationError: Si un valor numérico no es válido.
    """
    threads_dir = _get_path(env, "THREADS_DIR", DEFAULT_THREADS_DIR, project_root)
    alarm_rules_file = _get_path(env, "ALARM_RULES_FILE", DEFAULT_ALARM_RULES_FILE, project_root)
    return ConversationSettings(
        context_messages=_get_int(env, "THREAD_CONTEXT_MESSAGES", DEFAULT_THREAD_CONTEXT_MESSAGES),
        show_thread_debug=_get(env, "SHOW_THREAD_DEBUG", DEFAULT_SHOW_THREAD_DEBUG).lower()
        in TRUE_VALUES,
        threads_dir=threads_dir,
        alarm_rules_file=alarm_rules_file,
    )


def load_ollama_settings(env: Mapping[str, str]) -> OllamaSettings:
    """Construye la configuración de Ollama a partir de las variables `OLLAMA_*`.

    Las variables vacías o ausentes toman su valor por defecto.

    Args:
        env: Variables de entorno (normalmente `os.environ`).

    Returns:
        Configuración validada.

    Raises:
        ConfigurationError: Si un valor numérico no es válido.
    """
    return OllamaSettings(
        base_url=_get(env, "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/"),
        model=_get(env, "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        timeout_seconds=_get_float(env, "OLLAMA_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        temperature=_get_float(env, "OLLAMA_TEMPERATURE", DEFAULT_TEMPERATURE),
        num_ctx=_get_int(env, "OLLAMA_NUM_CTX", DEFAULT_NUM_CTX),
    )


def _get(env: Mapping[str, str], name: str, default: str) -> str:
    """Devuelve la variable sin espacios, o el valor por defecto si está vacía."""
    return env.get(name, "").strip() or default


def _get_float(env: Mapping[str, str], name: str, default: str) -> float:
    """Lee una variable como número decimal."""
    raw = _get(env, name, default)
    try:
        return float(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} debe ser un número, se recibió '{raw}'.") from error


def _get_int(env: Mapping[str, str], name: str, default: str) -> int:
    """Lee una variable como número entero."""
    raw = _get(env, name, default)
    try:
        return int(raw)
    except ValueError as error:
        raise ConfigurationError(
            f"{name} debe ser un número entero, se recibió '{raw}'."
        ) from error


def _get_path(env: Mapping[str, str], name: str, default: str, project_root: Path) -> Path:
    """Lee una ruta; si es relativa, se resuelve desde la raíz del proyecto."""
    path = Path(_get(env, name, default))
    return path if path.is_absolute() else project_root / path
