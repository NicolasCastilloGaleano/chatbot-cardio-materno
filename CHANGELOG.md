# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Fixed
- **MIG-04:** el verificador de respaldo ya no exime las frases de remisión: una frase hecha solo de "acude a urgencias o llama al 123" pasaba siempre, aunque el registro citado no lo dijera (causa U1). Se retiran `REFERRAL_WORDS` y `SAFE_NUMBERS` de `domain/grounding.py` (ADR 0010).

### Changed
- **Textos de abstención más claros (ADR 0010):** sin evidencia suficiente, "Todavía no tengo suficiente información para orientarte…" (con la pregunta de MIG-03); con el RAG no disponible, "En este momento no puedo consultar la información para orientarte…". Ya no mencionan "información del proyecto" ni "validada".
- **MIG-03:** con búsqueda insuficiente, la abstención (sin LLM) pide más detalles con una pregunta; con el RAG no disponible se mantiene el texto anterior (`UNAVAILABLE_TEXT`, ADR 0010).

### Fixed
- **El texto literal se muestra sin el prefijo** "Según la información validada del proyecto:" (ADR 0010). Que la respuesta es literal sigue en la traza.
- **Texto literal del registro más parecido (ADR 0010):** si la redacción no se verifica, el texto literal sale del registro de mayor similitud y no del primero que citó el agente. En la prueba del 2026-10-24, "tengo acidez en el embarazo" mostraba el aviso de un registro de preeclampsia que pedía mencionar hipertensión.

### Changed
- **MIG-01 del [plan de migración](docs/00-gestion/plan-migracion-rag2.md):** la respuesta a una pregunta pendiente del asistente ("sí, desde ayer", "no sé") ya no se descarta como fuera de alcance cuando el análisis la marca como continuación del hilo y el último mensaje del asistente contiene una pregunta (`scope.py::answers_pending_question`, ADR 0009).
- **MIG-02:** el turno fuera de alcance se registra en el hilo activo sin cambiarlo (sin hilo no se registra ni abre uno) y el mensaje fijo termina en una pregunta de reenganche (ADR 0009). La web solo lo muestra como no guardado si no había hilo, para no duplicarlo, y la línea de depuración de la consola ya no dice que no se registra.

### Added
- **Especificación propuesta de la auditoría multicanal (B-024):** HU-10 (chats por persona de todos los canales, carga por partes, colores por hilo, solo lectura para WhatsApp y Telegram, consola y web continuables en la interfaz) y ADR 0016. Aprobados el 2026-10-18.
- **HU-10, fase 2 (dominio, aplicación y SQLite):**
  - Canal `historico`, canales de solo lectura y regla `chat_lock` (`domain/user.py`).
  - Esquema SQLite v2 con migración automática (`users.live_session_at`).
  - `UserConversations`, que concentra la regla de inactividad y la creación del servicio por usuario (WhatsApp ahora la usa).
  - `DirectChat` y `ConsoleChatSession` para chats de consola y web.
  - Puerto `ChatAudit` + `SqliteChatAudit`: lista de chats, páginas por *keyset*, alertas por turno y mensajes en proceso.
  - `ThreadRepository.all_alerts`.
  - Importación única del histórico JSON (`run_import_history.py`), idempotente.
  - Configuración común `PersistenceSettings` (`DATABASE_PATH`, `THREAD_IDLE_TIMEOUT_HOURS`).
  - La consola y la web todavía no usan estos componentes (fases 3 a 5).
- **HU-10, fases 3 y 4 (consola y API web sobre SQLite):**
  - **Consola** (`bootstrap/console.py`): cada arranque crea un chat en SQLite, muestra su identificador y lo bloquea para la web mientras está abierta. Al salir cierra el hilo y lo libera. `ConsoleChat` recibe la sesión por un `Protocol`.
  - **API web nueva:** lista de chats con filtro por canal, chat nuevo, páginas por `before`/`after`, mensajes en proceso, envío con 403 en chats de solo lectura y 409 si ya hay un turno en curso, y liberación de chats de consola.
  - El contrato JSON pasa a `serializers.py`.
  - Variables `WEB_PAGE_SIZE` y `WEB_POLL_SECONDS`.
- **HU-10, fase 5 (interfaz gráfica):** tres columnas (chats, conversación, auditoría).
  - Filtros por canal y chats de solo lectura con candado.
  - Mensajes de cada hilo con su color y separadores donde cambia el hilo.
  - Carga hacia arriba por páginas conservando la posición.
  - Actualización automática con "procesando…" y "mensajes nuevos".
  - Composer bloqueado con el motivo y botón "Liberar".
  - Mensajes fuera de alcance mostrados como no guardados.
  - Respuesta seleccionada resaltada; chat abierto recordado en el navegador; diseño para pantallas angostas.
- **Especificación propuesta del canal WhatsApp (B-010):** HU-09 (atención por WhatsApp con historial por persona), ADR 0014 (WhatsApp Cloud API con webhook firmado, cola de un trabajador y ngrok) y ADR 0015 (SQLite con usuarios, identidad seudonimizada con HMAC e hilos acotados por usuario, sin cambiar el agente). Aprobados por el equipo el 2026-10-17.
- **Persistencia SQLite por usuario (HU-09, fase 2, ADR 0015):** entidades `User`, `Channel` y la regla `is_idle` (`domain/user.py`); puertos `UserDirectory`, `UserThreadStore` y `ChannelLog`; adaptadores `SqliteDatabase` (esquema versionado, transacciones, WAL), `SqliteThreadRepository` acotado a un usuario, `SqliteUserThreadStore`, `SqliteUserDirectory` y `SqliteChannelLog`. Sin dependencias nuevas (`sqlite3` de la biblioteca estándar). Aún no la usa ningún canal: la consola y la web siguen con JSON.
- **Canal WhatsApp (HU-09, fase 3, ADR 0014):** `python run_whatsapp.py` (`bootstrap/whatsapp.py`).
  - Webhook FastAPI con verificación de Meta, firma `X-Hub-Signature-256` obligatoria, 200 inmediato y `/health`.
  - Cola de un trabajador (`MessageDispatcher`) que procesa en orden de llegada.
  - Caso de uso `HandleIncomingMessage`: usuario por HMAC del número, deduplicación, acuse de lectura con "escribiendo…", cierre del hilo inactivo, servicio acotado al usuario, aviso de espera, respuestas largas en varias partes y registro sin texto.
  - Envío con `WhatsAppCloudSender` (Graph API, biblioteca estándar).
  - Nuevos `IncomingMessage`, el puerto `MessageSender`/`DelayedActions` y `ChannelDeliveryError`.
  - Sin dependencias nuevas.
- Variables `.env` (secciones 9 y 10): `WHATSAPP_APP_SECRET`, `WHATSAPP_API_VERSION`, `WHATSAPP_HOST`, `WHATSAPP_PORT`, `WHATSAPP_SEND_TIMEOUT_SECONDS`, `WHATSAPP_WAIT_NOTICE_SECONDS`, `WHATSAPP_MAX_PENDING`, `USER_ID_HASH_SECRET`, `DATABASE_PATH`, `THREAD_IDLE_TIMEOUT_HOURS`. El servidor solo escucha en loopback; ngrok publica la URL.
- Guía paso a paso de Meta Developers, ngrok y el webhook en `instalacion.md`, incluida la suscripción de la cuenta de WhatsApp Business a la app (`subscribed_apps`), sin la cual los mensajes reales no llegan.
- **HU-09 verificada en el PC de pruebas (2026-10-18)** con el número de prueba de Meta y dos teléfonos. ADR 0014 actualizado con el posible cobro de los mensajes de servicio desde octubre de 2026 (pendiente de confirmar en la facturación de Meta).
- `ConversationService` acepta `active_thread_id` (opcional) para retomar el hilo abierto de un usuario; sin él, se comporta exactamente igual que antes.
- Pruebas: contrato común de `ThreadRepository` (JSON y SQLite, `test_thread_repository_contract.py`), aislamiento entre usuarios, un hilo abierto por usuario, deduplicación y dos personas conversando de forma intercalada con el mismo contexto que en la consola.

### Removed
- Rutas web `POST /api/messages`, `POST /api/session/end`, `GET /api/threads` y `GET /api/threads/{id}`, reemplazadas por `/api/chats…` (HU-10). La consola ya no guarda en `data/threads` (JSON).

### Changed
- `bootstrap/main.py`: `build_conversation` arma los puertos y la configuración del agente; `build_service` la usa y la consola y la web no cambian. `load_web_settings` reutiliza la validación de host local y puerto.
- `.env.example`: la sección "Canales y persistencia (fases siguientes)" se reemplaza por "Canal WhatsApp" y "Persistencia por usuario"; `DATABASE_URL` pasa a ser `DATABASE_PATH`.
- **Prompt de análisis v6:** un mensaje que reporta un síntoma o malestar de origen incierto siempre está en alcance (caso real: "dolor muy fuerte en el brazo por que me asustó una gallina"); "fuera_de_alcance" queda solo para mensajes ajenos sin síntomas. La regla determinista de alcance ya no exige un dominio para respetar los síntomas reportados (ADR 0009, actualización). Casos nuevos en `tests/live/scope_cases.json`.

### Fixed
- Interfaz web (revisión de la rama `feat/interfaz-web-auditoria`): formato de `ruff` (la CI fallaba en los 4 commits, así que mypy y pytest no corrían); tildes dañadas por doble codificación en 5 archivos Python (p. ej., el título "demostración y auditoría" y el error "El mensaje no puede estar vacío"); `trace_to_dict` dividida según el estándar de funciones cortas; `use_utf8_streams` pasa a ser pública (antes se importaba una función privada).

### Added
- `WEB_HOST` y `WEB_PORT` en `.env` (sección 8); la configuración rechaza cualquier host que no sea local, porque la interfaz muestra datos de salud sin autenticación.
- `tests/unit/test_text_encoding.py`: detecta tildes dañadas por doble codificación en `src`, `tests`, `scripts`, `docs` y `knowledge`.

### Fixed
- El punto de entrada `run_web.py` agrega `src/` al `sys.path`, igual que `run_console.py`, para permitir ejecutar el proyecto sin instalarlo como paquete.

### Added
- **HU-08 / B-023:** interfaz web local con FastAPI para conversar con el agente, inspeccionar las trazas y evidencias completas por respuesta y consultar hilos guardados en modo de solo lectura. `python run_web.py` sirve en `127.0.0.1:8000`; se agregan FastAPI/Uvicorn y el ADR 0013.
- La interfaz indica cuándo el agente está procesando un mensaje y mantiene los paneles de auditoría e hilos visibles mientras el historial del chat se desplaza dentro de su área.
- Enter envía el mensaje desde el campo de chat; Shift+Enter conserva el salto de línea.

### Changed
- **ADR 0011 aceptado:** se midió la combinación elegida (análisis `mistral-small3.1:24b` + respuesta `qwen3:8b`): alcance 9/9, filtro 2 16/18, turno p50 de 46,5 s. Se prioriza la seguridad; la meta de 15 s queda como trabajo futuro. B-022 cerrado.

### Changed
- **Decisión de modelos (ADR 0011, 2026-10-12):** análisis `mistral-small3.1:24b`, respuesta `qwen3:8b` sin razonamiento (`.env.example`). Ronda 3 del benchmark registrada; falta medir la latencia de esa combinación exacta.
- **Umbral del RAG de 0,55 a 0,50** por decisión del equipo (`evidence_policy.json` v1.2.0).
- **Configuración en `.env`, ordenada por secciones:** cada etapa define su modelo, temperatura, contexto, tiempo de espera, razonamiento y límite de tokens (`OLLAMA_ANALYSIS_*` / `OLLAMA_REPLY_*`, con respaldo en las generales); los umbrales del RAG y de la verificación (`RAG_MIN_SIMILARITY`, `RAG_TOP_K`, `RAG_CANDIDATE_K`, `GROUNDING_*`) reemplazan a los del archivo de política. La consola muestra el umbral efectivo al arrancar. Convención registrada en AGENTS.md §3 y en `estandares-codigo.md`.

### Added
- **Códigos cerrados de signos (B-015, ADR 0012 aceptado provisionalmente para la demostración):** catálogo v0.5.0 con `code` y `examples` por regla; el análisis marca `reported_signs` (lista cerrada por `enum`, prompt de análisis v5) y el filtro 2 los cruza de forma exacta con las reglas, además de revisar los síntomas en texto. Alertas con el origen `agente_codigo`, traza `reported_signs` y línea `[signos marcados: …]`. Pendiente de ratificación del equipo y de aprobación clínica de los códigos y ejemplos.
- `OLLAMA_ANALYSIS_THINK` / `OLLAMA_REPLY_THINK`: razonamiento por etapa (respaldo en `OLLAMA_THINK`).

### Changed
- `scripts/benchmark_models.py` evalúa el filtro 2 por texto y por código, dice la vía de cada acierto y agrega la columna "Filtro 2 por código"; las pruebas en vivo usan el esquema con los códigos del catálogo.

### Changed
- Catálogo de alarmas **v0.4.0** (PROVISIONAL, implementado para la demostración por decisión de Nicolas y pendiente de aprobación clínica): se amplían los patrones de RN-MI-02/03/10/12/13/14 y RN-CV-03/06 para reconocer descripciones correctas que no activaban su regla (p. ej., "vómito de todo lo que come", "fiebre en bebé de 10 días", "soy hipertenso"). No cambian signos, severidades ni mensajes. Frases de referencia nuevas (positivas y negativas) en `alarm_phrases.json`.
- `scripts/benchmark_models.py` mide el filtro 2 por sí solo sobre las 18 frases coloquiales (mismo conjunto en todas las rondas) y marca las que también capta el filtro 1.
- HU-02 (respuesta verificada) y HU-07 (alcance) verificadas en el PC de pruebas y marcadas como ✅; B-008, B-018 y B-020 cerrados. Siguen abiertos B-021, B-022 (elección del modelo, ADR 0011) y B-015 (ADR 0012).

### Added
- `docs/00-gestion/pendientes-aprobacion.md`: lista única de lo que debe aprobar el equipo (catálogo v0.4.0, códigos de B-015, ADR 0012, frases coloquiales, preguntas clínicas, modelo y vacíos de la base), enlazada desde el README.
- ADR 0012 (Propuesto): signos reportados como códigos cerrados del catálogo (B-015), en paralelo con el texto libre. Pendiente de la decisión del equipo.

### Fixed
- Precalentamiento con las mismas opciones (`num_ctx`, `num_predict`) que las consultas: antes Ollama volvía a cargar el modelo en el primer turno (análisis de 37 s y RAG de 7,7 s en el guion del 2026-10-12).
- Marcadores del prompt copiados por el modelo ("[N] días", "[lo que describió la persona]"): `analysis_prompt_v4` los prohíbe; se quitan del resumen y de la consulta de búsqueda, y los síntomas que los traen quedan marcados en `unstated_symptoms`.

### Changed
- `scripts/benchmark_models.py` mide el filtro 2 con frases coloquiales que el filtro 1 no capta (`tests/live/colloquial_alarm_phrases.json`, PROVISIONAL) e imprime las frases descartadas de las respuestas con texto literal; la prueba en vivo del respaldo también las imprime.
- ADR 0011 con los resultados de la ronda 1 de la comparación de modelos; preguntas 3 y 4 en la solicitud de validación clínica.

### Added
- Latencia (B-022, ADR 0011 propuesto): precalentamiento de los modelos de análisis, respuesta y embeddings al arrancar; límite de tokens por etapa (`OLLAMA_ANALYSIS_NUM_PREDICT`=600, `OLLAMA_REPLY_NUM_PREDICT`=500); `OLLAMA_THINK` opcional.
- `scripts/benchmark_models.py`: compara combinaciones de modelos (alcance, filtro 2, respaldo y tiempos p50/p90) y guarda el informe en `data/benchmarks/`. Los casos de alcance pasan a `tests/live/scope_cases.json`, compartido con `test_live_scope.py`.

### Changed
- `OLLAMA_EMBED_NUM_GPU` vale `0` por defecto (embedder en CPU); `auto` deja decidir a Ollama.

### Added
- Análisis v3 (`analysis_prompt_v3`): nunca agregar datos que la persona no escribió; ejemplos con marcadores [N] en lugar de datos copiables; sin arrastre de síntomas a un hilo nuevo; campo `search_query` (consulta de salud reformulada sin el contexto ajeno) que pasa a ser la consulta de búsqueda (B-021).
- Marca de datos no dichos: `domain/grounding.py::unstated_details` registra en la traza (`unstated_symptoms`) los síntomas con números que la persona no escribió, con la línea `[⚠️ datos que la persona no escribió: …]`; la consulta usada queda en la traza (`search_query`) y en la línea `[búsqueda: …]`.
- Pruebas en vivo `tests/live/test_live_analysis.py` (incidentes de "34 semanas" y del arrastre, búsqueda antes vs. ahora) y sonda con métricas top-1 y "útil con el umbral real".

### Fixed
- Corrección de documentación: la sonda ya exigía la categoría esperada en el top-3; el problema de ACV y TVP es de orden y de umbral, no de categoría ausente (B-021).

### Added
- Respuesta verificada (ADR 0010, B-018): el LLM redacta frase por frase (`reply_prompt_v3`, `sentences: [{text, evidence_id}]`) y `domain/grounding.py` comprueba de forma determinista que cada frase citada esté respaldada por su registro (palabras con contenido ≥ `min_support` y todos los números). Si una frase no lo está, se muestra el texto literal del registro. Las frases sin cita solo se conservan si son preguntas cortas, cortesía o "no puedo ayudar con…".
- Traza `grounding` (frases mostradas, total, texto literal y frases descartadas) y línea de depuración `[respaldo: …]`.
- Prueba en vivo `tests/live/test_live_grounding.py`: arma el asistente completo con los modelos reales y comprueba que no reaparecen los consejos inventados del guion.

### Changed
- Sin evidencia suficiente (insuficiente o RAG no disponible) ya no se llama al LLM de respuesta: se muestra un mensaje fijo de abstención; con alarma prioritaria, solo su mensaje fijo.
- `knowledge/evidence_policy.json` v1.1.0: `min_support`, `max_free_sentences` y `max_free_words`.
- `bootstrap/main.py`: `build_service` pasa a ser público (lo usan las pruebas en vivo).

### Fixed
- Filtro 2: cada síntoma reportado se revisa por separado. Antes se unían en un solo texto, y "acidez en el embarazo" + "fiebre en el bebé" activaba RN-MI-07 (fiebre en el embarazo) con el mensaje para gestantes.
- Una urgencia detectada por el filtro 1 queda en el hilo activo solo si es del mismo dominio; si no, se abre un hilo con el dominio de la regla (antes un ACV quedaba en el hilo materno de la fiebre de un bebé).
- Los saludos y agradecimientos nunca abren un hilo: con hilo activo quedan en él sin cambiar su dominio ni su resumen, y sin hilo no se registran (línea de depuración `[sin hilo: mensaje conversacional · no se registra]`).

### Added
- Guion de verificación manual de HU-02/HU-07 actualizado en `docs/08-despliegue/instalacion.md` (abstención con una pregunta dentro del dominio, traza en el JSON del hilo, RAG no disponible y medición de latencia); B-021 en el backlog.
- HU-07: control de alcance por intención. El análisis devuelve `scope` (`en_alcance` / `conversacional` / `fuera_de_alcance`) y `scope_reason`. Los mensajes completamente ajenos reciben un mensaje fijo, sin RAG ni llamada de respuesta, y no se registran. Los saludos se responden sin RAG. Los temas mencionados como contexto no descartan el mensaje; los síntomas de nuestros dominios y las alarmas siempre tienen prioridad. Prompts `analysis_prompt_v2` y `reply_prompt_v2`, ADR 0009 y riesgo R-11.
- Latencia: `OLLAMA_KEEP_ALIVE` (30m) en todas las solicitudes y `OLLAMA_EMBED_NUM_GPU` (embedder en CPU); guía de diagnóstico en `docs/08-despliegue/operacion.md`.
- Pruebas en vivo de alcance (`tests/live/test_live_scope.py`).
- HU-02: orientación con evidencia (RAG). Base de 1.600 registros versionada en `knowledge/kb/entries.jsonl` (exportada del piloto con `scripts/export_pilot_kb.py`), índice propio con numpy (`run_build_kb_index.py`) y buscador híbrido (coseno + BM25 + RRF + umbral de `knowledge/evidence_policy.json`).
- Separación del agente en **dos llamadas**: análisis sin evidencia (hilo, resumen y síntomas → filtro 2) y respuesta con evidencia (`reply` + `evidence_ids` restringidos a las etiquetas ofrecidas). Prompts `analysis_prompt_v1` y `reply_prompt_v1`.
- Traza por respuesta (`trace`: síntomas, evidencia, citas, estado de la búsqueda, tiempos) y nuevas líneas de depuración `[evidencia …]` y `[tiempos …]`.
- Modelos por etapa (`OLLAMA_ANALYSIS_MODEL`, `OLLAMA_REPLY_MODEL`), cliente HTTP compartido de Ollama y embeddings (`/api/embed`) con división de lotes ante timeouts.
- Pruebas en vivo (`tests/live/`, `pytest -m live`): sonda de recuperación de 16 casos y no contaminación del análisis. ADR 0008, riesgo R-10, B-018 y B-019.
- HU-03/HU-04: alarmas deterministas con **doble filtro**. Las reglas revisan el mensaje del usuario (si hay urgencia inmediata no se consulta al LLM) y los `reported_symptoms` del agente. Mensajes fijos de urgencia o de consulta prioritaria, red de seguridad si falla el LLM, y alertas registradas en el hilo con su origen (`usuario`/`agente`).
- Catálogo PROVISIONAL de 20 reglas (`knowledge/alarm_rules.json`) validado al arrancar (`ALARM_RULES_FILE`), y frases de referencia (`tests/conversational/alarm_phrases.json`).
- Prompt v3 (`reported_symptoms`), ADR 0007, primer BPMN (`gestion-alerta.bpmn`), flujo de gestión de alerta, solicitud de validación clínica, riesgo R-09, entidad ALERT en el modelo y el diccionario de datos, y B-015/B-016 en el backlog.
- CI en GitHub Actions (`.github/workflows/ci.yml`): ruff, ruff format, mypy (`src` + `tests`) y pytest en cada push y PR.
- Auditoría de lineamientos (`docs/06-calidad/auditoria-lineamientos.md`) con su checklist y la primera ejecución; comando `/auditar-lineamientos`.
- Registro del sprint 1 (`docs/00-gestion/sprints/sprint-01.md`) con la sección de retro para el equipo.
- B-014 (foco actual del hilo) registrado en el backlog como diferido.
- HU-06: hilos conversacionales. El agente responde en JSON (`thread_action`, `domain`, `summary`, `reply`), decide si el mensaje continúa el hilo o abre uno nuevo y mantiene un resumen. Cada mensaje guarda su `thread_id`.
- Contexto acotado por turno: JSON del hilo actual + últimos `THREAD_CONTEXT_MESSAGES` mensajes.
- Persistencia de hilos en `data/threads/<id>.json` (`JsonFileThreadRepository`) y línea de depuración `[hilo …]` en la consola (`SHOW_THREAD_DEBUG`).
- Prompt de sistema v2, ADR 0006 y riesgo R-08; modelo y diccionario de datos completos para THREAD y MESSAGE.
- HU-00: chat libre por consola con Ollama local (`python run_console.py`). Incluye historial en memoria, prompt de sistema v1, verificación del modelo al arrancar y mensajes de error claros en español.
- Puerto `LanguageModel`, caso de uso `ChatService`, adaptadores `OllamaLanguageModel` y `ConsoleChat`, y configuración desde `.env`.
- 29 pruebas unitarias (sin Ollama); `requirements-dev.txt` con pytest, ruff y mypy.
- ADR 0005 (Ollama local como LLM) y riesgo R-07 (prototipo sin reglas de alarma).
- Estructura inicial del repositorio con arquitectura hexagonal (carpetas vacías y un README por capa).
- `AGENTS.md` y `CLAUDE.md` con las reglas de trabajo, los estándares de código y el protocolo de cierre de tarea.
- Documentación base en `docs/`: charter, especificación, arquitectura, ADR 0001–0004, playbook y bitácora de IA, calidad, gobernanza y despliegue.
- Hook `Stop` de Claude Code (`.claude/hooks/check_docs.py`) y comando `/cerrar-tarea` para garantizar que la documentación se actualice.
- Plantilla de Pull Request con la checklist de la Definition of Done.

- B-017 registrado en el backlog: intención del mensaje (consulta vs. reporte) para adaptar la respuesta a una alarma sin suprimirla; pregunta agregada a la solicitud de validación clínica.

- HU-03/HU-04 verificadas técnicamente en el PC de pruebas; CI en verde. Las reglas siguen PROVISIONALES hasta la validación clínica.

- HU-02/HU-07: `pytest -m live` en verde en el PC de pruebas (17/17, sonda RAG 16/16). La sonda pasa por puntaje, pero en ACV y TVP recupera una categoría equivocada aunque la base sí los cubre (77 y 41 registros): es un problema del buscador (B-021). La diabetes gestacional no tiene registros en la base, y ampliarla es una decisión clínica. Queda pendiente el guion manual.

### Fixed
- Un saludo o agradecimiento dentro de un hilo ya no cambia el dominio del caso a `ninguno`.
- RAG: un registro hallado solo por BM25 podía pasar el umbral cuando este era 0 (sonda de calibración) y causar `KeyError`; ahora solo califican los registros con similitud vectorial (hallazgo de `pytest -m live`).
- RN-MI-02 no captaba en el filtro 1 "me duele mucho la cabeza" ni "veo como estrellitas" (solo alertaba por el filtro 2). Catálogo v0.3.1 + frases de regresión.
- Alarma no detectada cuando el agente reportó "disminución de los movimientos del bebé" (hallazgo 2 de la prueba manual). Catálogo v0.3.0 con más variantes de RN-MI-06. Puente hacia B-015: el prompt v5 incluye los nombres exactos de los signos del catálogo y cada regla coincide con su propio nombre. B-015 pasa a prioridad Alta como solución definitiva.
- Alarma no detectada con "me está saliendo como agüita rosada por abajo, tengo 7 meses" (hallazgo de la prueba manual). Catálogo v0.2.0: secreción, flujo o líquido rosado o sanguinolento, contexto de embarazo "tengo N meses/semanas" y salida de líquido más flexible. Prompt v4: los síntomas reportados deben ser literales y completos. Frases de regresión agregadas.
- `reported_symptoms` ahora se registra en cada respuesta del asistente (JSON del hilo) y se muestra en la línea de depuración (`[síntomas reportados por el agente: …]`).

### Changed
- `numpy` es la primera dependencia de ejecución (`requirements.txt`, ADR 0008). En Ubuntu se ejecuta dentro de `.venv`. La guía de instalación se reescribió para Ubuntu.
- `ConversationService` recibe `ConversationPorts` + `ConversationConfig`; `TurnResult.reported_symptoms` se reemplaza por `trace`. En el JSON del hilo, `reported_symptoms` pasa a `trace.reported_symptoms` (los archivos anteriores se siguen leyendo).
- El resumen del hilo lo escribe la llamada de análisis: cada respuesta entra al resumen en el turno siguiente (ADR 0006).
- `ConversationService` recibe un `ConversationConfig` (se elimina `# noqa: PLR0913`); `HttpResponse` (Protocol) tipa el `opener` del adaptador de Ollama, y mypy ahora también verifica `tests/`.
- DoD, AGENTS.md §7 y playbook: mientras haya un solo desarrollador activo, su verificación basta para fusionar a `main`; la CI debe pasar.
- READMEs de `application` y `persistence` y el playbook actualizados (referencias obsoletas).
- HU-06 verificada en el PC de pruebas y marcada como aceptada.
- `ChatService` reemplazado por `ConversationService`; el puerto `LanguageModel` ahora expone `complete_json` (salida restringida por JSON Schema) en lugar de `reply`.
