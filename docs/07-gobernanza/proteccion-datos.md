# Protección de datos personales

*Última actualización: 2026-10-17*

Marco: **Ley 1581 de 2012** (Habeas Data), Decreto 1377 de 2013 y **Res. 2654 de 2019** (telesalud). Los datos de salud son **datos sensibles**.

## Principios aplicados
- **Consentimiento** explícito al inicio de la conversación (RN-01), registrado con fecha.
- **Minimización:** solo se guarda lo necesario. El identificador del canal se guarda como hash.
- **Anonimización** del texto antes de enviarlo al LLM y antes de guardarlo para métricas.
- **Seguridad:** cifrado en reposo de los campos sensibles, secretos en `.env` y HTTPS.
- **Sin datos reales** en el repositorio ni en las pruebas (solo datos sintéticos).

## Almacenamiento actual (HU-06)
- Los hilos se guardan en `data/threads/*.json` con el **texto completo** de los mensajes, que puede contener datos de salud. La carpeta está en `.gitignore` y **no se versiona**.
- Solo se usan **datos ficticios** en las pruebas; no se ingresan datos reales de personas.
- El prompt v2 pide que el resumen no incluya datos personales (nombre, documento, dirección, teléfono). Esto no es una garantía: falta la anonimización automática.

## RAG (HU-02)
- La consulta de búsqueda (mensaje + resumen + síntomas) se envía al modelo de embeddings de **Ollama local**; no sale del equipo.
- La base de conocimiento no contiene datos personales.
- La `trace` de cada respuesta incluye los síntomas reportados (datos de salud) y se guarda con el hilo, en `data/threads/`, que no se versiona.

## Interfaz web local (HU-08, HU-10, ADR 0013 y 0016)
- La interfaz muestra **todas** las conversaciones guardadas en `data/cardio_materno.db`, con su texto completo y sus trazas, que son datos de salud. **Desde la HU-10 esto incluye los chats de WhatsApp de las personas** (hoy solo números de prueba del equipo), además de la consola, la web y el histórico. **No tiene autenticación.**
- Los chats de WhatsApp y Telegram solo se auditan: el servidor rechaza escribir en ellos. Se identifican con un prefijo del identificador interno, nunca con el número ni el nombre, que no se guardan.
- Por eso solo puede escuchar en la propia máquina: `WEB_HOST` admite únicamente `127.0.0.1`, `localhost` o `::1`, y cualquier otra dirección impide arrancar (`bootstrap/settings.py::load_web_settings`).
- Es para demostración y depuración con datos ficticios. **No se expone en una red ni se usa con usuarios reales.** Antes de un piloto harían falta autenticación, cifrado y control de acceso por persona.

## Usuarios y base SQLite (HU-09, ADR 0015)
- **Identidad seudonimizada:** de cada canal solo se guarda `HMAC-SHA256(USER_ID_HASH_SECRET, identificador)`. No se guardan el teléfono ni el nombre de perfil de WhatsApp. El identificador en claro solo vive en memoria mientras se procesa el mensaje, para poder responder.
- **Aislamiento:** cada persona solo accede a sus propios hilos (repositorio acotado por usuario); hay pruebas automáticas que lo verifican.
- **Eventos sin texto:** el registro de mensajes recibidos y enviados (`inbound_events`, `outbound_messages`) solo guarda identificadores, tipos y estados.
- El texto de los mensajes y las trazas se guardan en `messages`, igual que en el JSON: datos de salud en un archivo (`data/cardio_materno.db`) que no se versiona.
- `USER_ID_HASH_SECRET` va en `.env` y se respalda junto con la base: si se pierde, las personas quedan desligadas de su historial.
- Esta fase es solo con números de prueba del equipo. El consentimiento (HU-01) es obligatorio antes de atender a personas reales.

## Pendientes
- TODO: texto del aviso de privacidad validado por los aliados.
- TODO: política de retención y eliminación (incluye borrar todos los datos de un usuario a petición suya).
- TODO: autorización de los aliados si alguna vez se usan datos reales con servicios de IA.
