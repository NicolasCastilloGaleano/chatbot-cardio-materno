"""Pruebas de la configuración y del cargador de `.env`."""

import os
from pathlib import Path

import pytest

from cardio_materno.application.stage_timer import StageTimer
from cardio_materno.bootstrap.env_file import load_env_file, parse_env_line
from cardio_materno.bootstrap.settings import (
    DEFAULT_OLLAMA_MODEL,
    ConfigurationError,
    load_conversation_settings,
    load_ollama_settings,
    load_rag_settings,
    load_stage_settings,
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
