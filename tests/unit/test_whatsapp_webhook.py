"""Pruebas del webhook, el payload y la firma de WhatsApp (HU-09, ADR 0014). Datos sintéticos."""

import hashlib
import hmac
import json
from functools import partial
from typing import Any

from fastapi.testclient import TestClient

from cardio_materno.adapters.inbound.whatsapp.payload import parse_messages
from cardio_materno.adapters.inbound.whatsapp.signature import is_valid_signature
from cardio_materno.adapters.inbound.whatsapp.webhook import (
    WEBHOOK_PATH,
    WebhookSecrets,
    create_whatsapp_app,
)
from cardio_materno.application.incoming_message import (
    IncomingMessage,
    MessageKind,
    make_identity_hasher,
)
from cardio_materno.domain.user import Channel

SECRETS = WebhookSecrets("token-de-verificacion", "app-secret")
HASH = make_identity_hasher("secreto")
WA_ID = "573000000001"


def message(kind: str = "text", **extra: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {"from": WA_ID, "id": f"wamid.{kind}", "timestamp": "1", "type": kind}
    if kind == "text":
        raw["text"] = {"body": "  tengo acidez  "}
    return raw | extra


def payload(*messages: dict[str, Any], statuses: list[Any] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "contacts": [{"profile": {"name": "Persona Ficticia"}, "wa_id": WA_ID}],
        "messages": list(messages),
    }
    if statuses is not None:
        value = {"messaging_product": "whatsapp", "statuses": statuses}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": value}]}],
    }


def signed(body: bytes, secret: str = SECRETS.app_secret) -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


def make_client(accept: bool = True) -> tuple[TestClient, list[IncomingMessage]]:
    queued: list[IncomingMessage] = []

    def submit(item: IncomingMessage) -> bool:
        if accept:
            queued.append(item)
        return accept

    app = create_whatsapp_app(SECRETS, partial(parse_messages, hasher=HASH), submit)
    return TestClient(app), queued


# --- Verificación (GET) ----------------------------------------------------------------


def test_verification_returns_the_challenge_with_the_right_token() -> None:
    client, _ = make_client()

    response = client.get(
        WEBHOOK_PATH,
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": SECRETS.verify_token,
            "hub.challenge": "1158201444",
        },
    )

    assert response.status_code == 200
    assert response.text == "1158201444"


def test_verification_with_a_wrong_token_is_rejected() -> None:
    client, _ = make_client()

    response = client.get(
        WEBHOOK_PATH,
        params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "1"},
    )

    assert response.status_code == 403


def test_health_check() -> None:
    client, _ = make_client()

    assert client.get("/health").json() == {"status": "ok"}


# --- Notificaciones (POST) -------------------------------------------------------------


def test_signed_notification_is_queued_and_acknowledged_at_once() -> None:
    client, queued = make_client()
    body = json.dumps(payload(message())).encode()

    response = client.post(WEBHOOK_PATH, content=body, headers=signed(body))

    assert response.status_code == 200
    assert queued == [
        IncomingMessage(
            Channel.WHATSAPP,
            "wamid.text",
            HASH(WA_ID),
            WA_ID,
            MessageKind.TEXT,
            "text",
            "tengo acidez",
        )
    ]


def test_unsigned_or_badly_signed_notification_is_rejected() -> None:
    client, queued = make_client()
    body = json.dumps(payload(message())).encode()

    unsigned = client.post(WEBHOOK_PATH, content=body)
    forged = client.post(WEBHOOK_PATH, content=body, headers=signed(body, "otro-secreto"))

    assert (unsigned.status_code, forged.status_code) == (401, 401)
    assert queued == []


def test_invalid_json_is_rejected() -> None:
    client, _ = make_client()
    body = b"no es json"

    assert client.post(WEBHOOK_PATH, content=body, headers=signed(body)).status_code == 400


def test_full_queue_asks_meta_to_retry() -> None:
    client, _ = make_client(accept=False)
    body = json.dumps(payload(message())).encode()

    assert client.post(WEBHOOK_PATH, content=body, headers=signed(body)).status_code == 503


def test_status_notifications_produce_no_messages() -> None:
    client, queued = make_client()
    body = json.dumps(payload(statuses=[{"id": "wamid.x", "status": "read"}])).encode()

    assert client.post(WEBHOOK_PATH, content=body, headers=signed(body)).status_code == 200
    assert queued == []


# --- Payload --------------------------------------------------------------------------


def test_non_text_messages_are_unsupported_and_reactions_are_silent() -> None:
    parsed = parse_messages(payload(message("image"), message("audio"), message("reaction")), HASH)

    assert [(item.channel_kind, item.kind) for item in parsed] == [
        ("image", MessageKind.UNSUPPORTED),
        ("audio", MessageKind.UNSUPPORTED),
    ]


def test_empty_text_is_treated_as_unsupported() -> None:
    parsed = parse_messages(payload(message(text={"body": "   "})), HASH)

    assert parsed[0].kind is MessageKind.UNSUPPORTED


def test_profile_name_and_phone_are_not_part_of_the_identity() -> None:
    item = parse_messages(payload(message()), HASH)[0]

    assert WA_ID not in item.user_hash
    assert "Persona Ficticia" not in repr(item)


def test_malformed_payloads_are_ignored() -> None:
    assert parse_messages({}, HASH) == []
    assert parse_messages({"entry": "x"}, HASH) == []
    assert parse_messages(payload({"type": "text"}), HASH) == []


# --- Firma e identidad ----------------------------------------------------------------


def test_signature_requires_prefix_secret_and_exact_match() -> None:
    body = b"{}"
    good = signed(body)["X-Hub-Signature-256"]

    assert is_valid_signature(body, good, SECRETS.app_secret)
    assert not is_valid_signature(body, None, SECRETS.app_secret)
    assert not is_valid_signature(body, good.removeprefix("sha256="), SECRETS.app_secret)
    assert not is_valid_signature(body, good, "")
    assert not is_valid_signature(b"{ }", good, SECRETS.app_secret)


def test_identity_hash_is_stable_and_depends_on_the_secret() -> None:
    assert HASH(WA_ID) == HASH(WA_ID)
    assert HASH(WA_ID) != make_identity_hasher("otro")(WA_ID)
    assert len(HASH(WA_ID)) == 64
