"""Pruebas de la configuración y del cargador de `.env`."""

import os
from pathlib import Path

import pytest

from cardio_materno.bootstrap.env_file import load_env_file, parse_env_line
from cardio_materno.bootstrap.settings import (
    DEFAULT_OLLAMA_MODEL,
    ConfigurationError,
    load_conversation_settings,
    load_ollama_settings,
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
