"""Lectura de la configuración desde variables de entorno."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
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
DEFAULT_RAG_ENABLED = "true"
DEFAULT_KEEP_ALIVE = "30m"
DEFAULT_EMBED_MODEL = "qwen3-embedding:8b"
DEFAULT_EMBED_TIMEOUT_SECONDS = "120"
DEFAULT_EMBED_BATCH_SIZE = "16"
DEFAULT_KB_ENTRIES_FILE = "knowledge/kb/entries.jsonl"
DEFAULT_KB_INDEX_DIR = "data/kb_index"
DEFAULT_EVIDENCE_POLICY_FILE = "knowledge/evidence_policy.json"
DEFAULT_EMBED_NUM_GPU = "0"
AUTO_VALUE = "auto"
ANALYSIS_MODEL_VARIABLE = "OLLAMA_ANALYSIS_MODEL"
REPLY_MODEL_VARIABLE = "OLLAMA_REPLY_MODEL"
# Límite de tokens por etapa (variable, valor por defecto). Holgado: el JSON del análisis
# suele ocupar 150-250 tokens y la respuesta (~90 palabras en frases) unos 250.
STAGE_NUM_PREDICT = {
    ANALYSIS_MODEL_VARIABLE: ("OLLAMA_ANALYSIS_NUM_PREDICT", "600"),
    REPLY_MODEL_VARIABLE: ("OLLAMA_REPLY_NUM_PREDICT", "500"),
}
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


@dataclass(frozen=True)
class RagSettings:
    """Configuración de la recuperación de evidencia (HU-02, ADR 0008).

    Attributes:
        enabled: Si se busca evidencia (si no, el agente se abstiene en temas de salud).
        embed_model: Modelo de embeddings de Ollama.
        embed_timeout_seconds: Tiempo máximo por solicitud de embeddings.
        embed_batch_size: Textos por solicitud al construir el índice.
        entries_file: Base de conocimiento versionada (`entries.jsonl`).
        index_dir: Carpeta del índice vectorial (derivado, no versionado).
        policy_file: Política de evidencia (umbral, top-k, instrucción de consulta).
        keep_alive: Tiempo que Ollama mantiene cargado el modelo de embeddings.
        embed_num_gpu: Capas del embedder en GPU (0 = CPU, por defecto; None = decide Ollama).
    """

    enabled: bool
    embed_model: str
    embed_timeout_seconds: float
    embed_batch_size: int
    entries_file: Path
    index_dir: Path
    policy_file: Path
    keep_alive: str = DEFAULT_KEEP_ALIVE
    embed_num_gpu: int | None = None


def load_rag_settings(env: Mapping[str, str], project_root: Path) -> RagSettings:
    """Construye la configuración del RAG a partir de las variables de entorno.

    Raises:
        ConfigurationError: Si un valor numérico no es válido.
    """
    return RagSettings(
        enabled=_get(env, "RAG_ENABLED", DEFAULT_RAG_ENABLED).lower() in TRUE_VALUES,
        embed_model=_get(env, "OLLAMA_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        embed_timeout_seconds=_get_float(
            env, "OLLAMA_EMBED_TIMEOUT_SECONDS", DEFAULT_EMBED_TIMEOUT_SECONDS
        ),
        embed_batch_size=_get_int(env, "EMBED_BATCH_SIZE", DEFAULT_EMBED_BATCH_SIZE),
        entries_file=_get_path(env, "KB_ENTRIES_FILE", DEFAULT_KB_ENTRIES_FILE, project_root),
        index_dir=_get_path(env, "KB_INDEX_DIR", DEFAULT_KB_INDEX_DIR, project_root),
        policy_file=_get_path(
            env, "EVIDENCE_POLICY_FILE", DEFAULT_EVIDENCE_POLICY_FILE, project_root
        ),
        keep_alive=_get(env, "OLLAMA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE),
        embed_num_gpu=_get_int_or_auto(env, "OLLAMA_EMBED_NUM_GPU", DEFAULT_EMBED_NUM_GPU),
    )


def load_stage_settings(env: Mapping[str, str], model_variable: str) -> OllamaSettings:
    """Configuración de Ollama para una etapa (análisis o respuesta).

    Si la variable de modelo de la etapa está vacía, se usa OLLAMA_MODEL. El límite de tokens
    sale de OLLAMA_ANALYSIS_NUM_PREDICT u OLLAMA_REPLY_NUM_PREDICT ("auto" = sin límite).

    Args:
        env: Variables de entorno.
        model_variable: Variable del modelo de la etapa (p. ej., OLLAMA_ANALYSIS_MODEL).

    Raises:
        ConfigurationError: Si un valor numérico no es válido.
    """
    base = load_ollama_settings(env)
    predict_variable, predict_default = STAGE_NUM_PREDICT.get(model_variable, ("", AUTO_VALUE))
    num_predict = _get_int_or_auto(env, predict_variable, predict_default)
    return replace(base, model=_get(env, model_variable, base.model), num_predict=num_predict)


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
        keep_alive=_get(env, "OLLAMA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE),
        think=_get_optional_bool(env, "OLLAMA_THINK"),
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


def _get_int_or_auto(env: Mapping[str, str], name: str, default: str) -> int | None:
    """Lee una variable entera; "auto" significa que decide Ollama (None)."""
    raw = _get(env, name, default) if name else default
    if raw.lower() == AUTO_VALUE:
        return None
    return _get_int(env, name, raw)


def _get_optional_bool(env: Mapping[str, str], name: str) -> bool | None:
    """Lee una variable booleana opcional (None si está vacía)."""
    raw = env.get(name, "").strip()
    return raw.lower() in TRUE_VALUES if raw else None
