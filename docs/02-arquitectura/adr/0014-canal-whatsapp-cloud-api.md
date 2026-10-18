# ADR 0014: Canal WhatsApp con Cloud API, webhook y cola de un trabajador

- **Estado:** Aceptado (2026-10-17)
- **Fecha:** 2026-10-17
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano)

## Contexto
El ADR 0003 fija WhatsApp como canal del prototipo final y pide que cada adaptador convierta sus mensajes a un `IncomingMessage` común y use el mismo caso de uso. El equipo ya tiene una app en Meta Developers con un número de prueba.

WhatsApp impone condiciones que la consola y la web no tienen:
- Meta **empuja** los mensajes a una URL pública HTTPS (webhook) y espera una respuesta 200 rápida. Si no la recibe, reenvía la notificación, así que un mismo mensaje puede llegar varias veces.
- Un turno del agente tarda unos 45 s (p50, ADR 0011), mucho más de lo que Meta espera.
- Ollama corre en el PC de pruebas, que no tiene una IP pública (ADR 0005 dejó abierta esta decisión).
- Se pueden recibir mensajes de varias personas a la vez, pero Ollama atiende las solicitudes de a una (8 GB de VRAM y dos modelos).

## Decisión
1. **API:** WhatsApp Cloud API de Meta (Graph API), versión configurable en `WHATSAPP_API_VERSION`. Envío con `urllib.request`, igual que el cliente de Ollama, **sin dependencias nuevas**.
2. **Webhook en FastAPI** (servidor propio `run_whatsapp.py`, separado de la web de auditoría):
   - `GET /webhooks/whatsapp` responde el `hub.challenge` si el `hub.verify_token` coincide con `WHATSAPP_VERIFY_TOKEN`; si no, 403.
   - `POST /webhooks/whatsapp` verifica la firma `X-Hub-Signature-256` (HMAC-SHA256 del cuerpo crudo con `WHATSAPP_APP_SECRET`, comparación en tiempo constante; 401 si falla), convierte el payload a `IncomingMessage`, lo **encola y responde 200 de inmediato**.
3. **Cola con un solo trabajador** (`queue.Queue` + un hilo): procesa en orden de llegada, lo que respeta el orden de cada persona y coincide con la capacidad real de Ollama. Tiene tamaño máximo y apagado limpio.
4. **Caso de uso común `HandleIncomingMessage`** (en `application/`), independiente del canal: deduplica por identificador del mensaje, resuelve el usuario, cierra el hilo inactivo, construye un `ConversationService` acotado al usuario (ADR 0015), envía la respuesta por el puerto `MessageSender` y registra el resultado.
5. **Espera:** al recibir el mensaje se marca como leído con indicador de "escribiendo…"; si la respuesta tarda más de `WHATSAPP_WAIT_NOTICE_SECONDS` (10 s por defecto), se envía un aviso corto de plantilla.
6. **Exposición:** el servidor escucha solo en loopback (se mantiene el criterio del ADR 0013) y **ngrok** con dominio estático gratuito publica la URL HTTPS desde el PC de pruebas. Ollama sigue en ese PC.
7. **Alcance de esta fase:** solo texto; los demás tipos reciben un aviso de plantilla. Solo los números de prueba del equipo (modo desarrollo de Meta). Sin consentimiento (HU-01), sin mensajes proactivos ni plantillas fuera de la ventana de 24 h.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Procesar dentro de la solicitud del webhook | Más simple | Meta reintenta al no recibir el 200 a tiempo y se duplican respuestas |
| Cola externa (Redis, Celery) | Robusta y escalable | Dependencias y servicios nuevos sin necesidad real: Ollama es el cuello de botella |
| Varios trabajadores en paralelo | Menos espera con varias personas | Ollama serializa igual; más intercambio de modelos en VRAM |
| Cloudflare Tunnel | Gratis, sin cuenta en modo rápido | La URL rápida cambia en cada arranque; el equipo eligió ngrok |
| Servidor/VPS público | URL estable y siempre disponible | Ollama tendría que ser accesible desde fuera; más costo y trabajo |
| Proveedor intermedio (Twilio, etc.) | SDK y panel listos | Costo, otra dependencia y otro tercero con datos de salud |

## Consecuencias
- ✅ El agente no cambia: el canal solo traduce mensajes y entrega respuestas.
- ✅ Los reenvíos de Meta no duplican respuestas (deduplicación persistente, ADR 0015).
- ✅ Sin dependencias de ejecución nuevas.
- ⚠️ Con varias personas a la vez, la espera se acumula (≈ 45 s por turno en cola). El aviso de espera lo mitiga; reducir la latencia sigue pendiente (ADR 0011).
- ⚠️ Un endpoint público con datos de salud: la firma de Meta es obligatoria y los secretos van solo en `.env`. El token temporal de Meta dura 24 h; para pruebas largas se usa un token de usuario del sistema.
- ⚠️ Si el proceso se reinicia con mensajes en cola, esos mensajes quedan como "recibidos" sin respuesta; se marcarán como interrumpidos al arrancar.
- Pendiente: consentimiento (HU-01), mensajes proactivos (`AlertNotifier`, B-016), audio e imágenes.

## Actualización 2026-10-18: verificación y costo de los mensajes
- **Verificado en el PC de pruebas** con el número de prueba de Meta, ngrok y dos teléfonos (HU-09 aceptada). Durante la configuración, la cuenta de WhatsApp Business no enviaba los mensajes reales al webhook hasta suscribirla a la app con `POST /{WABA_ID}/subscribed_apps`; el paso quedó en `instalacion.md`.
- **Costo:** según varias fuentes externas, desde el **1 de octubre de 2026** Meta cobra los mensajes de servicio (texto libre dentro de la ventana de 24 h) por encima de **1.000 al mes por número**. La página oficial de precios consultada no lo mostraba aún, así que **hay que confirmarlo en la facturación de la cuenta** antes del piloto. El número de prueba no factura.
- **Consecuencia para el diseño:** cada turno envía en promedio unos 2 mensajes (el aviso de espera, que con la latencia actual sale casi siempre, más la respuesta). Las 1.000 gratis alcanzarían para unas 500 consultas al mes. El consumo se mide en `outbound_messages` por `kind`. Desactivar o espaciar el aviso (`WHATSAPP_WAIT_NOTICE_SECONDS`) y bajar la latencia (ADR 0011) son decisiones del equipo para el piloto.
