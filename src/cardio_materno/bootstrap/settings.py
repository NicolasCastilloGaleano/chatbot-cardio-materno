"""Lectura de la configuración desde variables de entorno."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
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
DEFAULT_KB_CASES_FILE = "knowledge/kb/cuadros.jsonl"
DEFAULT_EVIDENCE_POLICY_FILE = "knowledge/evidence_policy.json"
DEFAULT_EMBED_NUM_GPU = "0"
AUTO_VALUE = "auto"
ANALYSIS_MODEL_VARIABLE = "OLLAMA_ANALYSIS_MODEL"
REPLY_MODEL_VARIABLE = "OLLAMA_REPLY_MODEL"
# Prefijo de las variables de cada etapa: OLLAMA_ANALYSIS_TEMPERATURE, OLLAMA_REPLY_MODEL…
STAGE_PREFIXES = {
    ANALYSIS_MODEL_VARIABLE: "OLLAMA_ANALYSIS_",
    REPLY_MODEL_VARIABLE: "OLLAMA_REPLY_",
}
# Variables que cada etapa puede definir; si la de la etapa está vacía, se usa la general
# OLLAMA_<CAMPO> (p. ej., OLLAMA_REPLY_TEMPERATURE vacía → OLLAMA_TEMPERATURE).
STAGE_FIELDS = ("MODEL", "TEMPERATURE", "NUM_CTX", "TIMEOUT_SECONDS", "THINK")
GLOBAL_PREFIX = "OLLAMA_"
NUM_PREDICT_FIELD = "NUM_PREDICT"
# Límite de tokens por defecto de cada etapa. Holgado: el JSON del análisis suele ocupar
# 150-250 tokens y la respuesta (~90 palabras en frases) unos 250.
STAGE_NUM_PREDICT_DEFAULTS = {ANALYSIS_MODEL_VARIABLE: "600", REPLY_MODEL_VARIABLE: "500"}
MIN_FRACTION = 0.0
MAX_FRACTION = 1.0
TRUE_VALUES = frozenset({"true", "1", "si", "sí", "yes"})
# Interfaz web local (ADR 0013): solo puede escuchar en la propia máquina.
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = "8000"
# Auditoría multicanal (ADR 0016): mensajes por página y frecuencia de la actualización.
DEFAULT_WEB_PAGE_SIZE = "30"
DEFAULT_WEB_POLL_SECONDS = "3"
MAX_WEB_PAGE_SIZE = 200
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MIN_PORT = 1
MAX_PORT = 65535
# Canal WhatsApp (ADR 0014) y base SQLite por usuario (ADR 0015).
DEFAULT_WHATSAPP_HOST = "127.0.0.1"
DEFAULT_WHATSAPP_PORT = "8001"
DEFAULT_WHATSAPP_API_VERSION = "v23.0"
DEFAULT_WHATSAPP_SEND_TIMEOUT_SECONDS = "15"
DEFAULT_WHATSAPP_WAIT_NOTICE_SECONDS = "10"
DEFAULT_WHATSAPP_MAX_PENDING = "100"
DEFAULT_THREAD_IDLE_TIMEOUT_HOURS = "12"
DEFAULT_DATABASE_PATH = "data/cardio_materno.db"
DEFAULT_LOG_LEVEL = "INFO"
WHATSAPP_REQUIRED = (
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_APP_SECRET",
    "USER_ID_HASH_SECRET",
)


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
class PolicyOverrides:
    """Umbrales de la política de evidencia fijados en .env (None = el del archivo).

    Attributes:
        min_similarity: `RAG_MIN_SIMILARITY`, similitud mínima para contar como evidencia.
        top_k: `RAG_TOP_K`, máximo de registros que se entregan al agente.
        candidate_k: `RAG_CANDIDATE_K`, candidatos por búsqueda antes de fusionar.
        min_support: `GROUNDING_MIN_SUPPORT`, respaldo mínimo de una frase citada.
        max_free_sentences: `GROUNDING_MAX_FREE_SENTENCES`, frases sin cita permitidas.
        max_free_words: `GROUNDING_MAX_FREE_WORDS`, palabras de una frase sin cita.
        case_top_k: `RAG_CASE_TOP_K`, registros por turno con la base v2 (ADR 0018).
    """

    min_similarity: float | None = None
    top_k: int | None = None
    candidate_k: int | None = None
    min_support: float | None = None
    max_free_sentences: int | None = None
    max_free_words: int | None = None
    case_top_k: int | None = None


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
        cases_file: Cuadros de la base v2 (`cuadros.jsonl`, ADR 0017). Solo se lee si la
            base tiene cuadros; con la base v1 se ignora.
        keep_alive: Tiempo que Ollama mantiene cargado el modelo de embeddings.
        embed_num_gpu: Capas del embedder en GPU (0 = CPU, por defecto; None = decide Ollama).
        policy_overrides: Umbrales de la política de evidencia definidos en .env, que
            reemplazan a los del archivo de política.
    """

    enabled: bool
    embed_model: str
    embed_timeout_seconds: float
    embed_batch_size: int
    entries_file: Path
    index_dir: Path
    policy_file: Path
    cases_file: Path
    keep_alive: str = DEFAULT_KEEP_ALIVE
    embed_num_gpu: int | None = None
    policy_overrides: PolicyOverrides = field(default_factory=PolicyOverrides)


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
        cases_file=_get_path(env, "KB_CASES_FILE", DEFAULT_KB_CASES_FILE, project_root),
        keep_alive=_get(env, "OLLAMA_KEEP_ALIVE", DEFAULT_KEEP_ALIVE),
        embed_num_gpu=_get_int_or_auto(env, "OLLAMA_EMBED_NUM_GPU", DEFAULT_EMBED_NUM_GPU),
        policy_overrides=load_policy_overrides(env),
    )


def load_policy_overrides(env: Mapping[str, str]) -> PolicyOverrides:
    """Umbrales de la política de evidencia definidos en .env (vacíos = los del archivo).

    Raises:
        ConfigurationError: Si un valor no es numérico o una fracción está fuera de [0, 1].
    """
    return PolicyOverrides(
        min_similarity=_get_optional_fraction(env, "RAG_MIN_SIMILARITY"),
        top_k=_get_optional_positive_int(env, "RAG_TOP_K"),
        candidate_k=_get_optional_positive_int(env, "RAG_CANDIDATE_K"),
        min_support=_get_optional_fraction(env, "GROUNDING_MIN_SUPPORT"),
        max_free_sentences=_get_optional_positive_int(env, "GROUNDING_MAX_FREE_SENTENCES"),
        max_free_words=_get_optional_positive_int(env, "GROUNDING_MAX_FREE_WORDS"),
        case_top_k=_get_optional_positive_int(env, "RAG_CASE_TOP_K"),
    )


def load_stage_settings(env: Mapping[str, str], model_variable: str) -> OllamaSettings:
    """Configuración de Ollama para una etapa (análisis o respuesta).

    Cada etapa puede definir su modelo, temperatura, contexto, tiempo de espera y
    razonamiento (`OLLAMA_ANALYSIS_*` / `OLLAMA_REPLY_*`); si una variable de la etapa está
    vacía, se usa la general (`OLLAMA_*`). El límite de tokens es propio de cada etapa
    (`OLLAMA_ANALYSIS_NUM_PREDICT` / `OLLAMA_REPLY_NUM_PREDICT`; "auto" = sin límite).

    Args:
        env: Variables de entorno.
        model_variable: Variable del modelo de la etapa (p. ej., OLLAMA_ANALYSIS_MODEL).

    Raises:
        ConfigurationError: Si un valor numérico no es válido.
    """
    prefix = STAGE_PREFIXES.get(model_variable, GLOBAL_PREFIX)
    base = load_ollama_settings(stage_environment(env, prefix))
    predict_default = STAGE_NUM_PREDICT_DEFAULTS.get(model_variable, AUTO_VALUE)
    num_predict = _get_int_or_auto(env, prefix + NUM_PREDICT_FIELD, predict_default)
    return replace(base, num_predict=num_predict)


def stage_environment(env: Mapping[str, str], prefix: str) -> dict[str, str]:
    """Variables de entorno en las que las de la etapa reemplazan a las generales."""
    merged = dict(env)
    for field_name in STAGE_FIELDS:
        value = env.get(prefix + field_name, "").strip()
        if value:
            merged[GLOBAL_PREFIX + field_name] = value
    return merged


@dataclass(frozen=True)
class WebSettings:
    """Configuración de la interfaz web local (ADR 0013).

    Attributes:
        host: Dirección de escucha; solo se admite la propia máquina (loopback).
        port: Puerto TCP.
        page_size: Mensajes por página al abrir un chat o subir con el scroll.
        poll_seconds: Cada cuánto la interfaz busca mensajes nuevos.
    """

    host: str
    port: int
    page_size: int = int(DEFAULT_WEB_PAGE_SIZE)
    poll_seconds: float = float(DEFAULT_WEB_POLL_SECONDS)


def load_web_settings(env: Mapping[str, str]) -> WebSettings:
    """Lee `WEB_HOST`, `WEB_PORT`, `WEB_PAGE_SIZE` y `WEB_POLL_SECONDS`.

    Raises:
        ConfigurationError: Si el host no es local (la interfaz no se expone en la red), el
            puerto no es válido o el tamaño de página o la frecuencia están fuera de rango.
    """
    page_size = _get_int(env, "WEB_PAGE_SIZE", DEFAULT_WEB_PAGE_SIZE)
    if not 1 <= page_size <= MAX_WEB_PAGE_SIZE:
        raise ConfigurationError(
            f"WEB_PAGE_SIZE debe estar entre 1 y {MAX_WEB_PAGE_SIZE}, se recibió {page_size}."
        )
    poll_seconds = _get_float(env, "WEB_POLL_SECONDS", DEFAULT_WEB_POLL_SECONDS)
    if poll_seconds <= 0:
        raise ConfigurationError(
            f"WEB_POLL_SECONDS debe ser mayor que 0, se recibió {poll_seconds}."
        )
    return WebSettings(
        _get_loopback_host(env, "WEB_HOST", DEFAULT_WEB_HOST),
        _get_port(env, "WEB_PORT", DEFAULT_WEB_PORT),
        page_size,
        poll_seconds,
    )


@dataclass(frozen=True)
class PersistenceSettings:
    """Base SQLite por usuario, común a todos los canales (ADR 0015 y 0016).

    Attributes:
        database_path: Archivo SQLite (`DATABASE_PATH`).
        idle_timeout_hours: Inactividad que cierra el hilo abierto (`THREAD_IDLE_TIMEOUT_HOURS`).
    """

    database_path: Path
    idle_timeout_hours: float


def load_persistence_settings(env: Mapping[str, str], project_root: Path) -> PersistenceSettings:
    """Lee la ubicación de la base y la regla de inactividad.

    Raises:
        ConfigurationError: Si la inactividad no es un número.
    """
    return PersistenceSettings(
        database_path=_get_path(env, "DATABASE_PATH", DEFAULT_DATABASE_PATH, project_root),
        idle_timeout_hours=_get_float(
            env, "THREAD_IDLE_TIMEOUT_HOURS", DEFAULT_THREAD_IDLE_TIMEOUT_HOURS
        ),
    )


@dataclass(frozen=True)
class WhatsAppSettings:
    """Configuración del canal WhatsApp (ADR 0014) y de su base SQLite (ADR 0015).

    Attributes:
        token: Token de acceso de Meta.
        phone_number_id: Identificador del número emisor.
        verify_token: Token que se registra en Meta al configurar el webhook.
        app_secret: App Secret de Meta, para verificar las firmas.
        user_hash_secret: Secreto del HMAC que seudonimiza las identidades.
        api_version: Versión de la Graph API.
        host: Dirección de escucha (solo loopback; ngrok publica la URL).
        port: Puerto del webhook.
        send_timeout_seconds: Tiempo máximo de cada envío a Meta.
        wait_notice_seconds: Espera antes del aviso de "estoy revisando".
        max_pending: Mensajes en cola antes de pedir a Meta que reintente.
        log_level: Nivel de los registros del proceso.
        persistence: Base SQLite e inactividad.
    """

    token: str
    phone_number_id: str
    verify_token: str
    app_secret: str
    user_hash_secret: str
    api_version: str
    host: str
    port: int
    send_timeout_seconds: float
    wait_notice_seconds: float
    max_pending: int
    log_level: str
    persistence: PersistenceSettings


def load_whatsapp_settings(env: Mapping[str, str], project_root: Path) -> WhatsAppSettings:
    """Lee la configuración del canal WhatsApp.

    Raises:
        ConfigurationError: Si falta un secreto, el host no es local o un número no es válido.
    """
    missing = [name for name in WHATSAPP_REQUIRED if not env.get(name, "").strip()]
    if missing:
        raise ConfigurationError(f"Faltan variables en .env: {', '.join(missing)}.")
    return WhatsAppSettings(
        token=_get(env, "WHATSAPP_TOKEN", ""),
        phone_number_id=_get(env, "WHATSAPP_PHONE_NUMBER_ID", ""),
        verify_token=_get(env, "WHATSAPP_VERIFY_TOKEN", ""),
        app_secret=_get(env, "WHATSAPP_APP_SECRET", ""),
        user_hash_secret=_get(env, "USER_ID_HASH_SECRET", ""),
        api_version=_get(env, "WHATSAPP_API_VERSION", DEFAULT_WHATSAPP_API_VERSION),
        host=_get_loopback_host(env, "WHATSAPP_HOST", DEFAULT_WHATSAPP_HOST),
        port=_get_port(env, "WHATSAPP_PORT", DEFAULT_WHATSAPP_PORT),
        send_timeout_seconds=_get_float(
            env, "WHATSAPP_SEND_TIMEOUT_SECONDS", DEFAULT_WHATSAPP_SEND_TIMEOUT_SECONDS
        ),
        wait_notice_seconds=_get_float(
            env, "WHATSAPP_WAIT_NOTICE_SECONDS", DEFAULT_WHATSAPP_WAIT_NOTICE_SECONDS
        ),
        max_pending=_get_int(env, "WHATSAPP_MAX_PENDING", DEFAULT_WHATSAPP_MAX_PENDING),
        log_level=_get(env, "LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
        persistence=load_persistence_settings(env, project_root),
    )


def _get_loopback_host(env: Mapping[str, str], name: str, default: str) -> str:
    """Lee una dirección de escucha que solo puede ser la propia máquina."""
    host = _get(env, name, default)
    if host not in LOOPBACK_HOSTS:
        allowed = ", ".join(sorted(LOOPBACK_HOSTS))
        raise ConfigurationError(f"{name} debe ser local ({allowed}), se recibió '{host}'.")
    return host


def _get_port(env: Mapping[str, str], name: str, default: str) -> int:
    """Lee un puerto TCP válido."""
    port = _get_int(env, name, default)
    if not MIN_PORT <= port <= MAX_PORT:
        raise ConfigurationError(f"{name} debe estar entre 1 y 65535, se recibió '{port}'.")
    return port


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


def _get_optional_fraction(env: Mapping[str, str], name: str) -> float | None:
    """Lee una fracción entre 0 y 1 (umbrales); None si la variable está vacía."""
    if not env.get(name, "").strip():
        return None
    value = _get_float(env, name, "")
    if not MIN_FRACTION <= value <= MAX_FRACTION:
        raise ConfigurationError(f"{name} debe estar entre 0 y 1, se recibió '{value}'.")
    return value


def _get_optional_positive_int(env: Mapping[str, str], name: str) -> int | None:
    """Lee un entero mayor que 0; None si la variable está vacía."""
    if not env.get(name, "").strip():
        return None
    value = _get_int(env, name, "")
    if value < 1:
        raise ConfigurationError(f"{name} debe ser mayor que 0, se recibió '{value}'.")
    return value


def _get_int_or_auto(env: Mapping[str, str], name: str, default: str) -> int | None:
    """Lee una variable entera; "auto" significa que decide Ollama (None)."""
    raw = _get(env, name, default) if name else default
    if raw.lower() == AUTO_VALUE:
        return None
    return _get_int(env, name, raw)


def _get_optional_bool(env: Mapping[str, str], name: str) -> bool | None:
    """Lee una variable booleana opcional (None si está vacía)."""
    raw = env.get(name, "").strip() if name else ""
    return raw.lower() in TRUE_VALUES if raw else None
