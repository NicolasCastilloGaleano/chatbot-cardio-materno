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
| `reported_symptoms` | lista de string | Sí (solo en mensajes `assistant` cuando el agente fue consultado; ausente si no se le consultó) | Síntomas que el agente identificó en el turno (filtro 2, ADR 0007); `[]` si no hubo | **Sí: datos de salud** | `["secreción vaginal rosada en el embarazo de 7 meses"]` |

### Entidad: `ALERT` (alerta por signo de alarma, HU-03/HU-04)
Clase: `domain/alarms.py::Alert`. Se guarda dentro de `alerts` del hilo.

| Campo | Tipo | Nulo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|---|
| `rule_ids` | lista de string | No | Reglas del catálogo que se activaron | No | `["RN-MI-01"]` |
| `severity` | enum | No | Gravedad máxima de esas reglas: `urgencia_inmediata` o `consulta_prioritaria` | No (dato de salud agregado) | `urgencia_inmediata` |
| `origin` | enum | No | `usuario` (filtro 1, texto original) o `agente` (filtro 2, `reported_symptoms`) | No | `agente` |
| `created_at` | string ISO 8601 (UTC) | No | Momento del registro | No | `2026-10-10T19:16:31+00:00` |

### Contrato de respuesta del agente (no se persiste; ADR 0006 y 0007)
| Campo | Tipo | Descripción |
|---|---|---|
| `thread_action` | `continuar` \| `nuevo` | Si el mensaje sigue el hilo o abre otro |
| `domain` | `materno_infantil` \| `cardiovascular` \| `ninguno` | Dominio del hilo resultante |
| `summary` | string | Resumen actualizado del hilo |
| `reply` | string | Respuesta para el usuario (se descarta si hay urgencia inmediata) |
| `reported_symptoms` | lista de string | Síntomas que la persona reporta, literales y con contexto. Si corresponden a un signo del catálogo, empiezan por su nombre exacto. Se revisan con las reglas de alarma (filtro 2). En B-015 se complementará con códigos cerrados |
