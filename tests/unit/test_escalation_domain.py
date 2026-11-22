"""Pruebas de las reglas del caso escalado al profesional (HU-16, ADR 0022)."""

from datetime import UTC, datetime, timedelta

import pytest

from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.escalation import (
    CaseAction,
    CaseSnapshot,
    CaseStatus,
    InvalidCaseTransitionError,
    apply_action,
    open_case,
    with_new_gap,
)

NOW = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
WINDOW = timedelta(hours=24)
SNAPSHOT = CaseSnapshot(
    Domain.CARDIOVASCULAR, "Ardor de estómago.", ("ardor",), (), "ardor", "sin información", "", 0.5
)


def pending() -> object:
    return open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW)


def test_a_new_case_is_pending_notified_and_expires_after_the_window() -> None:
    case = open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW)

    assert (case.status, case.notified, case.gap_count) == (CaseStatus.PENDING, True, 1)
    assert case.is_open and case.expires_at == NOW + WINDOW
    assert not case.is_expired(NOW + WINDOW - timedelta(seconds=1))
    assert case.is_expired(NOW + WINDOW)


@pytest.mark.parametrize(
    ("action", "status"),
    [
        (CaseAction.APPROVE, CaseStatus.APPROVED),
        (CaseAction.MODIFY, CaseStatus.MODIFIED),
        (CaseAction.EXPIRE, CaseStatus.EXPIRED),
    ],
)
def test_a_pending_case_is_resolved_and_closed(action: CaseAction, status: CaseStatus) -> None:
    case = apply_action(open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW), action, NOW)

    assert case.status is status and not case.is_open and case.closed_at == NOW
    assert not case.is_expired(NOW + 2 * WINDOW)


def test_direct_contact_stays_open_until_it_is_closed() -> None:
    case = open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW)

    contact = apply_action(case, CaseAction.START_CONTACT, NOW)
    closed = apply_action(contact, CaseAction.CLOSE, NOW + timedelta(hours=1))

    assert contact.status is CaseStatus.IN_CONTACT and contact.is_open and contact.closed_at is None
    assert closed.status is CaseStatus.CLOSED and closed.closed_at == NOW + timedelta(hours=1)


@pytest.mark.parametrize(
    ("status_action", "action"),
    [
        (CaseAction.APPROVE, CaseAction.MODIFY),
        (CaseAction.START_CONTACT, CaseAction.APPROVE),
        (None, CaseAction.CLOSE),
    ],
)
def test_actions_that_do_not_apply_are_rejected(
    status_action: CaseAction | None, action: CaseAction
) -> None:
    case = open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW)
    if status_action is not None:
        case = apply_action(case, status_action, NOW)

    with pytest.raises(InvalidCaseTransitionError):
        apply_action(case, action, NOW)


def test_a_new_gap_adds_to_the_case_and_renews_the_window() -> None:
    later = NOW + timedelta(hours=5)

    case = with_new_gap(open_case("caso-1", "hilo-1", SNAPSHOT, NOW, WINDOW), later, WINDOW)

    assert case.gap_count == 2 and case.expires_at == later + WINDOW
