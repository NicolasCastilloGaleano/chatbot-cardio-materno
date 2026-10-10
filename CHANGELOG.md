# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added
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

### Fixed
- RN-MI-02 no captaba en el filtro 1 "me duele mucho la cabeza" ni "veo como estrellitas" (solo alertaba por el filtro 2). Catálogo v0.3.1 + frases de regresión.
- Alarma no detectada cuando el agente reportó "disminución de los movimientos del bebé" (hallazgo 2 de la prueba manual). Catálogo v0.3.0 con más variantes de RN-MI-06. Puente hacia B-015: el prompt v5 incluye los nombres exactos de los signos del catálogo y cada regla coincide con su propio nombre. B-015 pasa a prioridad Alta como solución definitiva.
- Alarma no detectada con "me está saliendo como agüita rosada por abajo, tengo 7 meses" (hallazgo de la prueba manual). Catálogo v0.2.0: secreción, flujo o líquido rosado o sanguinolento, contexto de embarazo "tengo N meses/semanas" y salida de líquido más flexible. Prompt v4: los síntomas reportados deben ser literales y completos. Frases de regresión agregadas.
- `reported_symptoms` ahora se registra en cada respuesta del asistente (JSON del hilo) y se muestra en la línea de depuración (`[síntomas reportados por el agente: …]`).

### Changed
- `ConversationService` recibe un `ConversationConfig` (se elimina `# noqa: PLR0913`); `HttpResponse` (Protocol) tipa el `opener` del adaptador de Ollama, y mypy ahora también verifica `tests/`.
- DoD, AGENTS.md §7 y playbook: mientras haya un solo desarrollador activo, su verificación basta para fusionar a `main`; la CI debe pasar.
- READMEs de `application` y `persistence` y el playbook actualizados (referencias obsoletas).
- HU-06 verificada en el PC de pruebas y marcada como aceptada.
- `ChatService` reemplazado por `ConversationService`; el puerto `LanguageModel` ahora expone `complete_json` (salida restringida por JSON Schema) en lugar de `reply`.
