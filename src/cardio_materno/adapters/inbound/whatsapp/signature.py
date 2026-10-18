"""Verificación de la firma de las notificaciones de Meta (`X-Hub-Signature-256`, ADR 0014)."""

import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def is_valid_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    """Indica si el cuerpo fue firmado por Meta con el App Secret de la aplicación.

    La comparación es en tiempo constante para no filtrar información de la firma.

    Args:
        body: Cuerpo crudo de la solicitud, tal como llegó.
        header: Valor de `X-Hub-Signature-256` ("sha256=<hex>"), o None si no vino.
        app_secret: `WHATSAPP_APP_SECRET`.

    Returns:
        True solo si la firma existe y coincide.
    """
    if not header or not header.startswith(SIGNATURE_PREFIX) or not app_secret:
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix(SIGNATURE_PREFIX))
