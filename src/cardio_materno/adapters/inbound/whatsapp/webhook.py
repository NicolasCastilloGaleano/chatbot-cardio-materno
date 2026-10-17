"""Webhook de WhatsApp Cloud API con FastAPI (HU-09, ADR 0014).

- `GET  /webhooks/whatsapp`: verificación de Meta (`hub.mode`, `hub.verify_token`,
  `hub.challenge`).
- `POST /webhooks/whatsapp`: notificaciones firmadas. Se verifica la firma, se encolan los
  mensajes y se responde 200 de inmediato; el agente se consulta después, en la cola.
- `GET  /health`: comprobación simple para el túnel (ngrok).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from cardio_materno.adapters.inbound.whatsapp.signature import is_valid_signature
from cardio_materno.application.incoming_message import IncomingMessage

WEBHOOK_PATH = "/webhooks/whatsapp"
HEALTH_PATH = "/health"
SIGNATURE_HEADER = "X-Hub-Signature-256"
SUBSCRIBE_MODE = "subscribe"
APP_TITLE = "Canal WhatsApp: asistente cardio-materno"

PayloadParser = Callable[[dict[str, Any]], list[IncomingMessage]]
Submit = Callable[[IncomingMessage], bool]


@dataclass(frozen=True)
class WebhookSecrets:
    """Secretos del webhook.

    Attributes:
        verify_token: Cadena que se registra en Meta al configurar el webhook.
        app_secret: App Secret de la app de Meta, para verificar las firmas.
    """

    verify_token: str
    app_secret: str


def create_whatsapp_app(secrets: WebhookSecrets, parse: PayloadParser, submit: Submit) -> FastAPI:
    """Crea la aplicación del webhook.

    Args:
        secrets: Token de verificación y App Secret.
        parse: Convierte el payload en mensajes normalizados.
        submit: Encola un mensaje; devuelve False si la cola está llena.

    Returns:
        Aplicación FastAPI, sin documentación pública.
    """
    app = FastAPI(title=APP_TITLE, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get(HEALTH_PATH)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(WEBHOOK_PATH, response_class=PlainTextResponse)
    def verify(request: Request) -> str:
        return verify_subscription(dict(request.query_params), secrets.verify_token)

    @app.post(WEBHOOK_PATH)
    async def receive(request: Request) -> dict[str, str]:
        body = await request.body()
        if not is_valid_signature(body, request.headers.get(SIGNATURE_HEADER), secrets.app_secret):
            raise HTTPException(status_code=401, detail="Firma inválida")
        enqueue_all(parse(decode_payload(body)), submit)
        return {"status": "recibido"}

    return app


def verify_subscription(params: dict[str, str], verify_token: str) -> str:
    """Responde la verificación de Meta.

    Returns:
        El `hub.challenge` si el modo es "subscribe" y el token coincide.

    Raises:
        HTTPException: 403 si el token o el modo no coinciden.
    """
    token_ok = bool(verify_token) and params.get("hub.verify_token") == verify_token
    if params.get("hub.mode") != SUBSCRIBE_MODE or not token_ok:
        raise HTTPException(status_code=403, detail="Verificación rechazada")
    return params.get("hub.challenge", "")


def decode_payload(body: bytes) -> dict[str, Any]:
    """Decodifica el JSON de la notificación.

    Raises:
        HTTPException: 400 si el cuerpo no es un objeto JSON.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="Cuerpo inválido") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Cuerpo inválido")
    return payload


def enqueue_all(messages: list[IncomingMessage], submit: Submit) -> None:
    """Encola los mensajes.

    Raises:
        HTTPException: 503 si la cola está llena; Meta reintenta y los ya encolados no se
            duplican (deduplicación por identificador).
    """
    for message in messages:
        if not submit(message):
            raise HTTPException(status_code=503, detail="Cola llena, reintente")
