"""Lectura de la configuración desde variables de entorno."""

from collections.abc import Mapping

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaSettings

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "mistral-small3.1:24b"
DEFAULT_TIMEOUT_SECONDS = "180"
DEFAULT_TEMPERATURE = "0.3"
DEFAULT_NUM_CTX = "4096"


class ConfigurationError(Exception):
    """Una variable de configuración tiene un valor inválido."""


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
