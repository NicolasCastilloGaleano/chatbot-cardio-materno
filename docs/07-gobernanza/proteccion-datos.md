# Protección de datos personales

*Última actualización: 2026-11-11*

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
- **Determinantes sociales (B-036):** con la ronda 2, las personas pueden contar datos sensibles (estatus migratorio, violencia, pertenencia étnica, situación económica). Se tratan como los demás datos de salud del hilo: no se envían fuera del equipo, la traza no se versiona y los registros de la base no piden esos datos, solo orientan sobre rutas.
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

## Pruebas en MareNostrum 5 (BSC, 2026-11-08)
- Las pruebas de consola pueden correr en MareNostrum 5 ([guía](../08-despliegue/marenostrum5.md)). Los servidores están en España y la carpeta del proyecto (GPFS) es compartida por el grupo `bsc08`.
- Allí solo se usan **datos sintéticos** del equipo: no se sube la base `data/cardio_materno.db` del PC de pruebas ni el `.env` con los secretos de WhatsApp. La base de MN5 se crea vacía.
- No se usan los canales con personas (WhatsApp) en MN5.
- TODO: si algún día se procesan allí datos de personas reales, se requiere la autorización correspondiente a una transferencia internacional (Ley 1581, art. 26).

## Consentimiento y minimización (ADR 0022, 2026-11-15)
- **Consentimiento (HU-01):** con `CONSENT_MODE=requerido`, WhatsApp y la vista ciudadana no procesan ni guardan nada hasta que la persona acepta; se guarda el estado y su fecha. Está **apagado por defecto** hasta que se apruebe el texto. Con personas reales es obligatorio activarlo.
- **Minimización (`domain/privacy.py`):** antes de las alarmas, del modelo y del guardado se reemplazan por una marca los teléfonos, correos, documentos, direcciones urbanas y nombres declarados ("me llamo …"). Límite conocido: un nombre o un dato escrito de otra forma no se detecta; no reemplaza la política de retención.
- **Vista ciudadana:** su API no entrega trazas ni chats de otras personas. El identificador de la conversación se guarda en el navegador de la persona; quien lo tenga puede leer esa conversación, por eso la interfaz sigue limitada a la propia máquina.

## Datos de acceso a la atención (ADR 0023, 2026-11-16)
Lo que una persona cuenta sobre su afiliación, sus dificultades para atenderse o su colesterol es un dato sensible. Se distinguen tres finalidades:

| Finalidad | Base | Qué se guarda |
|---|---|---|
| Atender la conversación | Consentimiento de la HU-01 | Los mensajes (ya minimizados) y la traza del turno |
| Operar la regla de acceso | La misma atención | Nada codificado. Solo el aviso que sí se mostró, cuyo texto ya está en la respuesta |
| Informes agregados | Autorización **aparte, opcional y revocable** (`users.research_consent`) | Los códigos de lo que dijo, en la traza |

- El modo `observar` no guarda códigos sin esa autorización: el equipo los ve solo en el turno en curso.
- El informe cuenta personas y no hilos, por el mes de cada mensaje y solo meses cerrados; omite los meses con menos de 10 personas, lista siempre todos los indicadores ("<5" incluye el cero), suprime un dato compartido por casi todo el mes y redondea los demás a múltiplos de 5.
- Estos controles reducen el riesgo, **no garantizan anonimato**. Si alguien retira su autorización, dos exportaciones del mismo mes pueden diferir en sus indicadores: cada mes cerrado se publica una sola vez (pendiente 20).
- Rechazar o retirar el consentimiento retira también la autorización para informes. En la web se hace desde «Mis datos»; en WhatsApp todavía no hay forma (pendiente 22).
- La copia que se crea antes de migrar el esquema (`*.respaldo-v*.db`) tiene los mismos datos que la base y se guarda y se borra con el mismo cuidado.
- **No es una estimación de Caldas** ni de un municipio: describe a quienes usaron el asistente y lo autorizaron.
- Riesgo residual: en un municipio pequeño, la combinación de mes e indicador raro puede acercarse a una persona aunque el conteo esté redondeado. Por eso el informe no desagrega por municipio ni por canal.
- La información general de emergencias (`/api/public/emergency`) se entrega sin sesión y sin recibir ningún dato.

## Pendientes
- TODO: borrar los códigos ya guardados de quien retira la autorización para informes (hoy deja de contar, pero siguen en sus trazas).
- TODO: ofrecer la autorización para informes también en WhatsApp, cuando se apruebe su texto.
- TODO: revisar los patrones de minimización y aprobar los textos del consentimiento (pendientes 9 y 14).
- TODO: cifrado de la base SQLite y control de acceso si la interfaz deja de ser local.
- TODO: texto del aviso de privacidad validado por los aliados.
- TODO: política de retención y eliminación (incluye borrar todos los datos de un usuario a petición suya).
- TODO: autorización de los aliados si alguna vez se usan datos reales con servicios de IA.
