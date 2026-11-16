# ADR 0022: Vista ciudadana, consentimiento, minimización y procedencia de la evidencia

- **Estado:** Propuesto e implementado para revisión (2026-11-15). Lo ratifica el equipo (AGENTS.md §5); mientras tanto todo queda PROVISIONAL en [pendientes de aprobación](../../00-gestion/pendientes-aprobacion.md), puntos 9, 13, 14 y 15
- **Fecha:** 2026-11-15
- **Decisores:** equipo del proyecto; el texto y el alcance del consentimiento, también los aliados y quien responda por la protección de datos
- **Modifica:** ADR 0013 y 0016 (la interfaz web era solo una herramienta de auditoría del equipo)
- **Historias:** HU-01, HU-16 y HU-17
- **Origen:** dos auditorías externas del 2026-11 (consentimiento sin barrera, texto sin anonimizar, procedencia que no llega al runtime, interfaz sin separación entre la persona y el equipo)

## Contexto
La convocatoria compromete un aplicativo validado técnica y culturalmente con la comunidad. La interfaz web mostraba a cualquiera las trazas del agente y los chats de todos los canales, así que no servía para una sesión de validación con personas. Además había tres brechas que bloquean cualquier uso con personas reales: el consentimiento existía como dato pero nada lo exigía; el texto de la persona llegaba al modelo y a la base con los identificadores que escribiera; y la respuesta no podía decir de qué fuente salía, porque `entries.jsonl` no guarda la fuente de cada registro.

## Decisión
1. **Dos vistas sobre el mismo servidor local, sin dependencias nuevas** (HTML, CSS y JavaScript propios; ADR 0002 y 0013 siguen vigentes).
   - `/` es la **vista ciudadana**: una conversación propia, pensada primero para el teléfono. Usa solo `/api/me/*`, que entrega el texto, el tipo de respuesta (normal, consulta prioritaria o urgencia) y las fuentes. **Nunca** entrega trazas, síntomas interpretados, puntajes ni chats de otros canales (`application/citizen_chat.py` solo opera sobre chats del canal web).
   - `/equipo` es la **vista del equipo**: la auditoría multicanal de la HU-10 y una bandeja con las alertas de todos los chats (HU-17).
   - El host sigue limitado a la propia máquina. La separación es de función y de datos expuestos, **no es un control de acceso**: publicar la interfaz en una red exige autenticación y un ADR propio.
   - Desde el 2026-11-16 la aplicación rechaza con 403 toda petición cuyo `Host` no sea local, que traiga un `Origin` ajeno o cabeceras de reenvío (`adapters/inbound/api/local_only.py`). Escuchar en loopback no bastaba: un túnel apuntado al puerto, una página externa con DNS rebinding o un `POST` sin cuerpo desde otra página llegaban a los chats y a las alertas. Consecuencia: la vista ciudadana tampoco se puede publicar con un túnel; una sesión con la comunidad se hace en el equipo donde corre.
2. **Consentimiento como barrera (HU-01).** Con `CONSENT_MODE=requerido`, WhatsApp y la vista ciudadana no atienden ni guardan ningún mensaje hasta que la persona acepta. La respuesta se lee con una regla determinista y estricta (`domain/consent.py`): solo un "sí" o un "no" claros cambian el estado; cualquier otro mensaje vuelve a mostrar la solicitud. Se guarda el estado y su fecha (`users.consent_at`, columna que ya existía). El valor por defecto es `apagado` porque el texto no está aprobado y hoy solo escriben los números de prueba del equipo.
3. **Minimización antes de todo (`domain/privacy.py`).** `ConversationService.send` quita del texto teléfonos, correos, documentos, direcciones y nombres declarados antes de las alarmas, del modelo y del guardado, y deja una marca fija (`[teléfono]`). Es una regla determinista que solo reconoce formatos de identificador: no toca cifras de salud.
4. **Procedencia en un archivo aparte (`knowledge/kb/provenance.json`).** Se genera con `scripts/build_kb_provenance.py` desde el historial de git, los CSV de la ronda 2 y el catálogo de fuentes. No se modifica `entries.jsonl`, porque cambiarlo invalida el índice vectorial. Cada registro tiene lote, estado de revisión del lote y fuentes citadas. La vista ciudadana muestra las fuentes de los registros que la respuesta cita; la del equipo, además, el lote y la revisión.

## Lo que este ADR no decide
- **El texto del consentimiento y de los rechazos** (`application/channel_messages.py`): borrador técnico pendiente de los aliados.
- **La mención del 123 antes de aceptar.** La solicitud incluye la línea de emergencias, pero una persona que describe una urgencia sin haber aceptado recibe la solicitud, no el aviso de la regla. Si las alarmas deben evaluarse antes del consentimiento es una decisión clínica y jurídica. Desde el ADR 0023, la información general de emergencias se puede leer sin sesión ni aceptación (`/api/public/emergency`).
- **Los patrones de minimización.** Son conservadores; un nombre escrito sin "me llamo" no se detecta. Su alcance lo revisa quien responda por la protección de datos.
- **Retención, borrado y cifrado** de la base: siguen pendientes (`proteccion-datos.md`).
- **La validación clínica de la base.** El estado de revisión que se muestra es el que el equipo registró por lote; ninguno es validación clínica.
- **El escalamiento a un profesional.** La bandeja de alertas es de lectura: nadie recibe una notificación.
- **La cola de WhatsApp sigue en memoria.** Hacerla durable exige guardar por un tiempo el número de quien escribe, lo que contradice el ADR 0015; se necesita una decisión del equipo.

## Consecuencias
- La persona puede retirar su aceptación desde «Mis datos» en la conversación; deja de ser atendida por ese medio y se retira también la autorización para informes. Lo ya guardado no se borra (retención pendiente).
- Al subir el esquema de una base con datos se guarda antes una copia (`<base>.respaldo-v<N>.db`): una versión anterior del programa no abre una base migrada. La copia tiene los mismos datos sensibles que la base.
- La misma conversación sirve para una sesión de validación con la comunidad y para la auditoría del equipo.
- El mensaje que se guarda puede diferir del que la persona escribió (marcas en lugar de identificadores).
- `provenance.json` hay que regenerarlo cuando cambie la base; `test_real_provenance_file_covers_the_documented_batches` falla si deja de coincidir con los lotes documentados.
- La interfaz anterior (`index.html`, `app.js`, `styles.css`) se reemplazó por `ciudadano.*`, `equipo.*` y `base.css`.

## Verificación
Automática: 845 pruebas, ruff y mypy --strict. Recorrido visual del 2026-11-15 con un agente guionizado y datos sintéticos (sin Ollama): bienvenida y consentimiento, respuesta con fuentes, urgencia, vista del equipo con procedencia y bandeja de alertas, en teléfono y escritorio, tema claro y oscuro, sin errores de consola. **Pendiente:** recorrido en el PC de pruebas con Ollama, lector de pantalla y validación con personas de la comunidad.
