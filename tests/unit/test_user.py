"""Pruebas de las entidades de usuario y la regla de inactividad (ADR 0015)."""

from datetime import UTC, datetime, timedelta

from cardio_materno.domain.user import ConsentStatus, is_idle, new_user, seen_user

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
