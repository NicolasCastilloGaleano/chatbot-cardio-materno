# Diccionario de datos

*Última actualización: 2026-10-10*

Almacenamiento actual: archivos JSON en `THREADS_DIR` (por defecto `data/threads/`), uno por hilo (ADR 0006). La carpeta **no se versiona** (`.gitignore`).

### Entidad: `THREAD` (hilo conversacional)
Clase: `domain/conversation.py::ConversationThread`. Archivo: `<id>.json`.

| Campo | Tipo | Nulo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|---|
| `id` | string (UUID v4) | No | Identificador único del hilo; también es el nombre del archivo | No | `5f2b183b-…` |
| `domain` | enum | No | Dominio de salud que asigna el agente: `materno_infantil`, `cardiovascular` o `ninguno` | No | `materno_infantil` |
| `summary` | string | No | Resumen del hilo generado por el agente (máx. ~3 oraciones; sin datos personales según el prompt v2) | Puede contener datos de salud | `Gestante de 5 meses con acidez; pregunta por alimentación.` |
| `status` | enum | No | `abierto` (hilo activo de la sesión) o `cerrado` (cambio de tema o fin de sesión) | No | `abierto` |
| `created_at` | string ISO 8601 (UTC) | No | Creación del hilo | No | `2026-10-10T17:07:37.168536+00:00` |
| `updated_at` | string ISO 8601 (UTC) | No | Última modificación del hilo | No | `2026-10-10T17:07:37.197817+00:00` |
| `messages` | lista de `MESSAGE` | No (puede estar vacía) | Mensajes del hilo en orden cronológico | — | — |
| `alerts` | lista de `ALERT` | No (puede estar vacía) | Alertas por signos de alarma registradas en el hilo | — | — |

### Entidad: `MESSAGE` (mensaje de un hilo)
Clase: `domain/conversation.py::ChatMessage`. Se guarda dentro de `messages` del hilo.

| Campo | Tipo | Nulo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|---|
| `thread_id` | string (UUID) | No | Hilo al que pertenece el mensaje | No | `5f2b183b-…` |
| `role` | enum | No | `user` (persona) o `assistant` (agente) | No | `user` |
| `content` | string | No | Texto original completo del mensaje | **Sí, puede contener datos personales y de salud** | `Tengo mucha acidez` |
| `created_at` | string ISO 8601 (UTC) | Sí | Momento en que se registró el turno | No | `2026-10-10T17:07:37.171542+00:00` |
| `trace` | objeto `TRACE` | Sí (solo en mensajes `assistant` cuando se consultó al agente) | Cómo se produjo la respuesta (ver TRACE). Los archivos anteriores con `reported_symptoms` a nivel de mensaje se siguen leyendo | **Sí: datos de salud** | ver TRACE |

### Entidad: `ALERT` (alerta por signo de alarma, HU-03/HU-04)
Clase: `domain/alarms.py::Alert`. Se guarda dentro de `alerts` del hilo.

| Campo | Tipo | Nulo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|---|
| `rule_ids` | lista de string | No | Reglas del catálogo que se activaron | No | `["RN-MI-01"]` |
| `severity` | enum | No | Gravedad máxima de esas reglas: `urgencia_inmediata` o `consulta_prioritaria` | No (dato de salud agregado) | `urgencia_inmediata` |
| `origin` | enum | No | `usuario` (filtro 1, texto original) o `agente` (filtro 2, `reported_symptoms`) | No | `agente` |
| `created_at` | string ISO 8601 (UTC) | No | Momento del registro | No | `2026-10-10T19:16:31+00:00` |

### Objeto: `TRACE` (traza de una respuesta, ADR 0007 y 0008)
Clase: `domain/trace.py::ReplyTrace`. Se serializa en `trace_codec.py`.

| Campo | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `reported_symptoms` | lista de string | Síntomas que identificó la llamada de análisis (filtro 2); `[]` si no hubo | `["secreción vaginal rosada en el embarazo de 7 meses"]` |
| `retrieval_status` | enum o null | `suficiente`, `insuficiente`, `no_disponible`; `null` si no se buscó (urgencia en el filtro 2) | `suficiente` |
| `best_score` | número o null | Mejor similitud coseno vista en la búsqueda | `0.71` |
| `evidence` | lista | Evidencia ofrecida: `{label, entry_id, score, category}` | `[{"label": "E1", "entry_id": "3f…", "score": 0.71, "category": "Presión arterial…"}]` |
| `evidence_ids` | lista de string | Etiquetas que el agente dijo usar | `["E1"]` |
| `uncited_reply` | booleano | `true` si había evidencia suficiente y no se citó ninguna (para auditar) | `false` |
| `timings` | objeto | Segundos por etapa: `análisis`, `RAG`, `respuesta` | `{"análisis": 3.1, "RAG": 0.4, "respuesta": 6.2}` |
| `scope` | enum o null | Alcance aplicado: `en_alcance`, `conversacional` (los `fuera_de_alcance` no se guardan) | `en_alcance` |
| `scope_reason` | string | Motivo corto de la decisión de alcance | `consulta de acidez en el embarazo` |
| `unstated_symptoms` | lista de string | Síntomas con números (semanas, meses, edades) que la persona no escribió en el hilo: el análisis los inventó o arrastró. Solo para auditar: el síntoma se sigue revisando con las reglas de alarma | `["acidez en el embarazo de 34 semanas"]` |
| `search_query` | string | Consulta con la que se buscó la evidencia ("" si no se buscó) | `presión arterial alta` |
| `grounding` | objeto o null | Verificación del respaldo (ADR 0010): `supported` (frases mostradas), `total` (frases redactadas), `literal` (se mostró el texto literal del registro) y `dropped` (frases descartadas). `null` si no hubo redacción con evidencia (abstención, urgencia o saludo) | `{"supported": 1, "total": 2, "literal": true, "dropped": ["Come yogur…"]}` |

### Entidad: `KNOWLEDGE_ENTRY` (base de conocimiento, `knowledge/kb/entries.jsonl`)
Clase: `domain/knowledge.py::KnowledgeEntry`. Contenido versionado en git; el índice vectorial derivado (`data/kb_index/`) no se versiona.

| Campo | Tipo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|
| `id` | string (SHA-256 del piloto) | Identificador estable | No | `91d3…` |
| `domain` | enum | `materno_infantil` o `cardiovascular` | No | `cardiovascular` |
| `category` | string | Una de 8 categorías por dominio | No | `Presión arterial y riesgo cardiovascular` |
| `focus` | enum | `Indagar` o `Solucionar` | No | `Solucionar` |
| `question` | string | Pregunta tipo | No | `Tengo hipertensión… ¿por qué necesito controles?` |
| `answer` | string | Respuesta (390–710 caracteres) generada con IA y validada para el prototipo | No | — |

### Contrato de respuesta del agente (no se persiste; ADR 0006, 0007 y 0008)
Desde el ADR 0008 hay dos llamadas: **análisis** (`thread_action`, `domain`, `summary`, `reported_symptoms` y, desde el ADR 0009, `scope` y `scope_reason`) y **respuesta**. Desde el ADR 0010, la respuesta con evidencia es `sentences` (lista de `{text, evidence_id}`); la de los saludos sigue siendo `reply` + `evidence_ids` vacío.
| Campo | Tipo | Descripción |
|---|---|---|
| `thread_action` | `continuar` \| `nuevo` | Si el mensaje sigue el hilo o abre otro |
| `domain` | `materno_infantil` \| `cardiovascular` \| `ninguno` | Dominio del hilo resultante |
| `summary` | string | Resumen actualizado del hilo |
| `reply` | string | (Llamada de respuesta) Texto para el usuario; no se pide si hay urgencia inmediata |
| `evidence_ids` | lista de string | (Saludos) Siempre vacía |
| `sentences` | lista de `{text, evidence_id}` | (Respuesta con evidencia) Frases para el usuario; `evidence_id` es la etiqueta del registro que respalda la frase (restringida por `enum` a las ofrecidas) o `ninguna`. Cada frase se verifica con `domain/grounding.py` |
| `search_query` | string | (Análisis, desde el v3) Consulta de salud reformulada en palabras claras y sin el contexto ajeno; es la consulta de búsqueda de evidencia. Vacía si no hay consulta de salud (entonces se usa mensaje + resumen + síntomas) |
| `reported_symptoms` | lista de string | Síntomas que la persona reporta, literales y con contexto. Si corresponden a un signo del catálogo, empiezan por su nombre exacto. Se revisan con las reglas de alarma (filtro 2). En B-015 se complementará con códigos cerrados |
