"""Pruebas de las entidades de usuario y la regla de inactividad (ADR 0015)."""

from datetime import UTC, datetime, timedelta

from cardio_materno.domain.user import (
    Channel,
    ChatLock,
    ConsentStatus,
    chat_lock,
    is_idle,
    new_user,
    seen_user,
)

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=UTC)
TIMEOUT = timedelta(hours=12)


def test_new_user_starts_with_pending_consent() -> None:
    user = new_user("u1", NOW)

    assert (user.created_at, user.last_seen_at) == (NOW, NOW)
    assert user.consent_status is ConsentStatus.PENDING


def test_seen_user_only_updates_last_contact() -> None:
    later = NOW + timedelta(hours=1)

    user = seen_user(new_user("u1", NOW), later)

    assert (user.created_at, user.last_seen_at) == (NOW, later)


def test_thread_is_idle_only_after_the_timeout() -> None:
    assert not is_idle(NOW, NOW + TIMEOUT, TIMEOUT)
    assert is_idle(NOW, NOW + TIMEOUT + timedelta(seconds=1), TIMEOUT)


def test_whatsapp_telegram_and_history_are_read_only() -> None:
    for channel in (Channel.WHATSAPP, Channel.TELEGRAM, Channel.HISTORICAL):
        assert chat_lock(channel, None) is ChatLock.CHANNEL
    assert chat_lock(Channel.WEB, None) is None
    assert chat_lock(Channel.CONSOLE, None) is None


def test_console_chat_is_locked_while_a_console_has_it_open() -> None:
    assert chat_lock(Channel.CONSOLE, NOW) is ChatLock.LIVE_CONSOLE
    assert chat_lock(Channel.WHATSAPP, NOW) is ChatLock.CHANNEL
