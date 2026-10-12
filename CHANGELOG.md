# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

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
