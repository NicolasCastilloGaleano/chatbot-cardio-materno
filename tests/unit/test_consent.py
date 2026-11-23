"""Consentimiento (HU-01): lectura de la respuesta y barrera en los canales de chat."""

import itertools
from pathlib import Path

import pytest

from cardio_materno.adapters.outbound.persistence.sqlite_channel_log import SqliteChannelLog
from cardio_materno.adapters.outbound.persistence.sqlite_database import SqliteDatabase
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError
from cardio_materno.adapters.outbound.rag.provenance_file import load_provenance, provenance_path
from cardio_materno.application.channel_messages import (
    CONSENT_ACCEPTED_TEXT,
    CONSENT_REJECTED_TEXT,
    CONSENT_REQUEST_TEXT,
)
from cardio_materno.application.handle_incoming_message import (
    ChannelConfig,
    ChannelPorts,
    HandleIncomingMessage,
)
from cardio_materno.application.incoming_message import IncomingMessage, MessageKind
from cardio_materno.bootstrap.settings import ConfigurationError, load_persistence_settings
from cardio_materno.domain.consent import ConsentAnswer, read_consent_answer
from cardio_materno.domain.user import Channel
from tests.unit.fakes import (
    URGENT_MESSAGE,
    FakeClock,
    FakeDelayedActions,
    FakeSender,
    ScriptedAgent,
    agent_json,
    make_alarm_policy,
    make_user_conversations,
)
from tests.unit.test_handle_incoming_message import ANA, HASH, IDLE, database, text

__all__ = ["database"]

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("answer", ["Sí", "si", "SÍ.", "Acepto", "sí acepto", "Sí, señor", "ok"])
def test_a_clear_yes_is_an_acceptance(answer: str) -> None:
    assert read_consent_answer(answer) is ConsentAnswer.ACCEPT


@pytest.mark.parametrize("answer", ["No", "no acepto", "No, gracias"])
def test_a_clear_no_is_a_rejection(answer: str) -> None:
    assert read_consent_answer(answer) is ConsentAnswer.REJECT


@pytest.mark.parametrize(
    "answer", ["sí, pero me duele el pecho", "tengo sangrado", "no sé", "¿para qué es?", ""]
)
def test_anything_else_keeps_consent_pending(answer: str) -> None:
    assert read_consent_answer(answer) is ConsentAnswer.UNCLEAR


# --- Barrera en el canal ----------------------------------------------------------------


def channel(
    database: SqliteDatabase, agent: ScriptedAgent
) -> tuple[HandleIncomingMessage, FakeSender]:
    clock, ids, sender = FakeClock(), itertools.count(1), FakeSender()
    conversations = make_user_conversations(
        agent, SqliteUserThreadStore(database), clock, IDLE, {"alarm_policy": make_alarm_policy()}
    )
    ports = ChannelPorts(
        SqliteUserDirectory(database), SqliteChannelLog(database), sender, FakeDelayedActions()
    )
    config = ChannelConfig(
        10.0, clock=clock, new_id=lambda: f"usuario-{next(ids)}", consent_required=True
    )
    return HandleIncomingMessage(ports, config, conversations), sender


def sent(sender: FakeSender) -> list[str]:
    return [body for _, body in sender.sent]


def stored_messages(database: SqliteDatabase) -> int:
    return int(database.query("SELECT COUNT(*) FROM messages")[0][0])


def test_first_contact_gets_the_request_and_nothing_is_processed(database: SqliteDatabase) -> None:
    agent = ScriptedAgent(agent_json("Orientación"))
    handler, sender = channel(database, agent)

    handler.handle(text(ANA, "m1", "tengo sangrado vaginal"))

    assert sent(sender) == [CONSENT_REQUEST_TEXT]
    assert stored_messages(database) == 0 and agent.calls == []
    status = database.query("SELECT status FROM inbound_events")[0]["status"]
    assert status == "consentimiento"


def test_after_accepting_the_next_message_is_attended(database: SqliteDatabase) -> None:
    handler, sender = channel(database, ScriptedAgent(agent_json("Orientación")))

    handler.handle(text(ANA, "m1", "hola"))
    handler.handle(text(ANA, "m2", "Sí"))
    handler.handle(text(ANA, "m3", "tengo sangrado vaginal"))

    assert sent(sender) == [CONSENT_REQUEST_TEXT, CONSENT_ACCEPTED_TEXT, URGENT_MESSAGE]
    row = database.query("SELECT consent_status, consent_at FROM users")[0]
    assert row["consent_status"] == "aceptado" and row["consent_at"]
    assert stored_messages(database) == 2


def test_a_rejection_is_recorded_and_can_be_changed_later(database: SqliteDatabase) -> None:
    handler, sender = channel(database, ScriptedAgent(agent_json("Orientación")))

    handler.handle(text(ANA, "m1", "no"))
    handler.handle(text(ANA, "m2", "tengo acidez"))
    handler.handle(text(ANA, "m3", "acepto"))

    assert sent(sender) == [CONSENT_REJECTED_TEXT, CONSENT_REQUEST_TEXT, CONSENT_ACCEPTED_TEXT]
    assert stored_messages(database) == 0


def test_a_voice_note_before_consent_gets_the_request(database: SqliteDatabase) -> None:
    handler, sender = channel(database, ScriptedAgent())
    audio = IncomingMessage(
        Channel.WHATSAPP, "m1", HASH(ANA), ANA, MessageKind.UNSUPPORTED, "audio", ""
    )

    handler.handle(audio)

    assert sent(sender) == [CONSENT_REQUEST_TEXT]


# --- Configuración y procedencia --------------------------------------------------------


def test_consent_mode_is_off_by_default_and_validated(tmp_path: Path) -> None:
    assert load_persistence_settings({}, tmp_path).consent_required is False
    assert load_persistence_settings({"CONSENT_MODE": "requerido"}, tmp_path).consent_required
    with pytest.raises(ConfigurationError):
        load_persistence_settings({"CONSENT_MODE": "tal vez"}, tmp_path)


def test_real_provenance_file_covers_the_documented_batches() -> None:
    provenance = load_provenance(provenance_path(REPO_ROOT / "knowledge" / "kb" / "entries.jsonl"))

    reviews = [record.review for record in provenance.records.values()]
    assert provenance.default.review == "validada_para_prototipo"
    assert reviews.count("pendiente_de_validacion") == 1228
    assert reviews.count("revisada_por_el_equipo") == 1221
    with_sources = [record for record in provenance.records.values() if record.sources]
    assert len(with_sources) == 1221
    assert all(source.url.startswith("http") for r in with_sources for source in r.sources)


def test_missing_provenance_claims_no_source(tmp_path: Path) -> None:
    provenance = load_provenance(tmp_path / "provenance.json")

    assert provenance.of("cualquiera").sources == ()
    assert provenance.of("cualquiera").review == "sin_registro"


def test_broken_provenance_file_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "provenance.json"
    path.write_text('{"sources": {}}', encoding="utf-8")

    with pytest.raises(KnowledgeBaseError):
        load_provenance(path)
