# adapter inbound: whatsapp

Canal WhatsApp Cloud API (HU-09, ADR 0014). Arranque: `python run_whatsapp.py`.

- `webhook.py`: FastAPI. GET de verificación de Meta, POST firmado (`X-Hub-Signature-256`) y `/health`.
- `signature.py`: verificación HMAC-SHA256 con el App Secret.
- `payload.py`: payload de Meta → `IncomingMessage` (sin nombre de perfil; el número solo se usa como hash y dirección de respuesta).
- `dispatcher.py`: cola de un trabajador y temporizador del aviso de espera.

El envío está en `adapters/outbound/whatsapp/cloud_sender.py`; la lógica del canal, en `application/handle_incoming_message.py`.