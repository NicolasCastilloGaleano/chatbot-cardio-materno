"""Pruebas de la configuración y del cargador de `.env`."""

import os
from pathlib import Path

import pytest

from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.stage_timer import StageTimer
from cardio_materno.bootstrap.env_file import load_env_file, parse_env_line
from cardio_materno.bootstrap.rag_setup import apply_policy_overrides
from cardio_materno.bootstrap.settings import (
    DEFAULT_OLLAMA_MODEL,
    ConfigurationError,
    WebSettings,
    load_conversation_settings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
    load_web_settings,
    load_whatsapp_settings,
)


def test_defaults_when_variables_missing_or_empty() -> None:
    settings = load_ollama_settings({"OLLAMA_MODEL": "  "})

    assert settings.base_url == "http://127.0.0.1:11434"
    assert settings.model == DEFAULT_OLLAMA_MODEL
    assert settings.timeout_seconds == 180
    assert settings.num_ctx == 4096


def test_values_are_read_from_environment() -> None:
    env = {
        "OLLAMA_BASE_URL": "http://pc-pruebas:11434/",
        "OLLAMA_MODEL": "llama3:8b",
        "OLLAMA_TIMEOUT_SECONDS": "60",
        "OLLAMA_TEMPERATURE": "0.1",
        "OLLAMA_NUM_CTX": "8192",
    }

    settings = load_ollama_settings(env)

    assert settings.base_url == "http://pc-pruebas:11434"
    assert settings.model == "llama3:8b"
    assert settings.timeout_seconds == 60
    assert settings.temperature == 0.1
    assert settings.num_ctx == 8192


def test_invalid_number_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="OLLAMA_NUM_CTX"):
        load_ollama_settings({"OLLAMA_NUM_CTX": "mucho"})


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("OLLAMA_MODEL=llama3", ("OLLAMA_MODEL", "llama3")),
        ('  KEY = "con comillas" ', ("KEY", "con comillas")),
        ("# comentario", None),
        ("", None),
        ("sin_igual", None),
    ],
)
def test_parse_env_line(line: str, expected: tuple[str, str] | None) -> None:
    assert parse_env_line(line) == expected


def test_load_env_file_does_not_override_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CM_TEST_A=archivo\nCM_TEST_B=archivo\n", encoding="utf-8")
    monkeypatch.setenv("CM_TEST_A", "entorno")
    monkeypatch.delenv("CM_TEST_B", raising=False)

    load_env_file(env_file)

    assert os.environ["CM_TEST_A"] == "entorno"
    assert os.environ["CM_TEST_B"] == "archivo"
    monkeypatch.delenv("CM_TEST_B")


def test_conversation_settings_defaults(tmp_path: Path) -> None:
    settings = load_conversation_settings({}, tmp_path)

    assert settings.context_messages == 6
    assert settings.show_thread_debug is True
    assert settings.threads_dir == tmp_path / "data" / "threads"
    assert settings.alarm_rules_file == tmp_path / "knowledge" / "alarm_rules.json"


def test_conversation_settings_from_environment(tmp_path: Path) -> None:
    env = {
        "THREAD_CONTEXT_MESSAGES": "10",
        "SHOW_THREAD_DEBUG": "false",
        "THREADS_DIR": str(tmp_path / "otros"),
    }

    settings = load_conversation_settings(env, tmp_path)

    assert settings.context_messages == 10
    assert settings.show_thread_debug is False
    assert settings.threads_dir == tmp_path / "otros"


def test_rag_settings_defaults(tmp_path: Path) -> None:
    settings = load_rag_settings({}, tmp_path)

    assert settings.enabled is True
    assert settings.embed_model == "qwen3-embedding:8b"
    assert settings.entries_file == tmp_path / "knowledge" / "kb" / "entries.jsonl"
    assert settings.index_dir == tmp_path / "data" / "kb_index"
    assert settings.policy_file == tmp_path / "knowledge" / "evidence_policy.json"


def test_rag_can_be_disabled(tmp_path: Path) -> None:
    assert load_rag_settings({"RAG_ENABLED": "false"}, tmp_path).enabled is False


def test_stage_model_falls_back_to_ollama_model() -> None:
    env = {"OLLAMA_MODEL": "grande:24b", "OLLAMA_ANALYSIS_MODEL": "pequeno:3b"}

    assert load_stage_settings(env, "OLLAMA_ANALYSIS_MODEL").model == "pequeno:3b"
    assert load_stage_settings(env, "OLLAMA_REPLY_MODEL").model == "grande:24b"


def test_stage_timer_records_duration_even_when_action_fails() -> None:
    ticks = iter([0.0, 1.25, 2.0, 2.5])
    timer = StageTimer(lambda: next(ticks))

    assert timer.measure("análisis", lambda: "ok") == "ok"
    with pytest.raises(ValueError):
        timer.measure("respuesta", lambda: (_ for _ in ()).throw(ValueError()))

    assert [(t.stage, t.seconds) for t in timer.timings] == [("análisis", 1.25), ("respuesta", 0.5)]


def test_latency_settings_defaults_and_overrides(tmp_path: Path) -> None:
    defaults = load_rag_settings({}, tmp_path)
    custom = load_rag_settings(
        {"OLLAMA_KEEP_ALIVE": "1h", "OLLAMA_EMBED_NUM_GPU": "auto"}, tmp_path
    )

    assert (defaults.keep_alive, defaults.embed_num_gpu) == ("30m", 0)
    assert (custom.keep_alive, custom.embed_num_gpu) == ("1h", None)


def test_stage_token_limits_have_defaults_and_can_be_disabled() -> None:
    env = {"OLLAMA_REPLY_NUM_PREDICT": "auto", "OLLAMA_ANALYSIS_NUM_PREDICT": ""}

    assert load_stage_settings(env, "OLLAMA_ANALYSIS_MODEL").num_predict == 600
    assert load_stage_settings(env, "OLLAMA_REPLY_MODEL").num_predict is None
    assert (
        load_stage_settings({"OLLAMA_REPLY_NUM_PREDICT": "300"}, "OLLAMA_REPLY_MODEL").num_predict
        == 300
    )


def test_think_is_optional() -> None:
    assert load_ollama_settings({}).think is None
    assert load_ollama_settings({"OLLAMA_THINK": "false"}).think is False
    assert load_ollama_settings({"OLLAMA_THINK": "true"}).think is True


def test_invalid_embed_num_gpu_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="OLLAMA_EMBED_NUM_GPU"):
        load_rag_settings({"OLLAMA_EMBED_NUM_GPU": "mucho"}, tmp_path)


def test_think_can_be_set_per_stage_with_global_fallback() -> None:
    env = {"OLLAMA_THINK": "true", "OLLAMA_ANALYSIS_THINK": "false"}

    assert load_stage_settings(env, "OLLAMA_ANALYSIS_MODEL").think is False
    assert load_stage_settings(env, "OLLAMA_REPLY_MODEL").think is True
    assert load_stage_settings({}, "OLLAMA_REPLY_MODEL").think is None


def test_each_stage_can_set_model_temperature_context_and_timeout() -> None:
    env = {
        "OLLAMA_MODEL": "general",
        "OLLAMA_TEMPERATURE": "0.3",
        "OLLAMA_ANALYSIS_MODEL": "mistral-small3.1:24b",
        "OLLAMA_ANALYSIS_TEMPERATURE": "0.1",
        "OLLAMA_REPLY_MODEL": "qwen3:8b",
        "OLLAMA_REPLY_NUM_CTX": "8192",
        "OLLAMA_REPLY_TIMEOUT_SECONDS": "60",
    }

    analysis = load_stage_settings(env, "OLLAMA_ANALYSIS_MODEL")
    reply = load_stage_settings(env, "OLLAMA_REPLY_MODEL")

    assert (analysis.model, analysis.temperature, analysis.num_ctx) == (
        "mistral-small3.1:24b",
        0.1,
        4096,
    )
    assert (reply.model, reply.temperature, reply.num_ctx, reply.timeout_seconds) == (
        "qwen3:8b",
        0.3,
        8192,
        60,
    )


def test_evidence_thresholds_from_env_override_the_policy_file(tmp_path: Path) -> None:
    env = {"RAG_MIN_SIMILARITY": "0.5", "RAG_TOP_K": "4", "GROUNDING_MIN_SUPPORT": " "}

    overrides = load_rag_settings(env, tmp_path).policy_overrides
    policy = apply_policy_overrides(EvidencePolicy(min_similarity=0.55, min_support=0.6), overrides)

    assert (overrides.min_similarity, overrides.top_k, overrides.min_support) == (0.5, 4, None)
    assert (policy.min_similarity, policy.top_k, policy.min_support) == (0.5, 4, 0.6)


@pytest.mark.parametrize(
    ("name", "value"),
    [("RAG_MIN_SIMILARITY", "1.5"), ("GROUNDING_MIN_SUPPORT", "-0.1"), ("RAG_TOP_K", "0")],
)
def test_invalid_evidence_thresholds_raise_configuration_error(
    tmp_path: Path, name: str, value: str
) -> None:
    with pytest.raises(ConfigurationError, match=name):
        load_rag_settings({name: value}, tmp_path)


def test_web_settings_default_to_loopback_and_accept_local_hosts() -> None:
    assert load_web_settings({}) == WebSettings("127.0.0.1", 8000)
    assert load_web_settings({"WEB_HOST": "localhost", "WEB_PORT": "8080"}) == WebSettings(
        "localhost", 8080
    )


@pytest.mark.parametrize(
    ("env", "name"),
    [({"WEB_HOST": "0.0.0.0"}, "WEB_HOST"), ({"WEB_PORT": "70000"}, "WEB_PORT")],
)
def test_web_settings_reject_network_hosts_and_invalid_ports(
    env: dict[str, str], name: str
) -> None:
    with pytest.raises(ConfigurationError, match=name):
        load_web_settings(env)


WHATSAPP_ENV = {
    "WHATSAPP_TOKEN": "t",
    "WHATSAPP_PHONE_NUMBER_ID": "123",
    "WHATSAPP_VERIFY_TOKEN": "v",
    "WHATSAPP_APP_SECRET": "s",
    "USER_ID_HASH_SECRET": "h",
}


def test_whatsapp_settings_defaults(tmp_path: Path) -> None:
    settings = load_whatsapp_settings(WHATSAPP_ENV, tmp_path)

    assert (settings.host, settings.port) == ("127.0.0.1", 8001)
    assert settings.api_version == "v23.0"
    assert settings.wait_notice_seconds == 10.0
    assert settings.persistence.idle_timeout_hours == 12.0
    assert settings.persistence.database_path == tmp_path / "data" / "cardio_materno.db"


def test_whatsapp_settings_require_every_secret(tmp_path: Path) -> None:
    env = WHATSAPP_ENV | {"WHATSAPP_APP_SECRET": " ", "USER_ID_HASH_SECRET": ""}

    with pytest.raises(ConfigurationError, match="WHATSAPP_APP_SECRET, USER_ID_HASH_SECRET"):
        load_whatsapp_settings(env, tmp_path)


def test_whatsapp_server_only_listens_on_loopback(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="WHATSAPP_HOST"):
        load_whatsapp_settings(WHATSAPP_ENV | {"WHATSAPP_HOST": "0.0.0.0"}, tmp_path)


def test_web_page_size_and_poll_interval() -> None:
    defaults = load_web_settings({})
    custom = load_web_settings({"WEB_PAGE_SIZE": "50", "WEB_POLL_SECONDS": "1.5"})

    assert (defaults.page_size, defaults.poll_seconds) == (30, 3.0)
    assert (custom.page_size, custom.poll_seconds) == (50, 1.5)
    with pytest.raises(ConfigurationError, match="WEB_PAGE_SIZE"):
        load_web_settings({"WEB_PAGE_SIZE": "0"})
    with pytest.raises(ConfigurationError, match="WEB_POLL_SECONDS"):
        load_web_settings({"WEB_POLL_SECONDS": "0"})
