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

### Entidad: `MESSAGE` (mensaje de un hilo)
Clase: `domain/conversation.py::ChatMessage`. Se guarda dentro de `messages` del hilo.

| Campo | Tipo | Nulo | Descripción | Sensible (PII) | Ejemplo |
|---|---|---|---|---|---|
| `thread_id` | string (UUID) | No | Hilo al que pertenece el mensaje | No | `5f2b183b-…` |
| `role` | enum | No | `user` (persona) o `assistant` (agente) | No | `user` |
| `content` | string | No | Texto original completo del mensaje | **Sí, puede contener datos personales y de salud** | `Tengo mucha acidez` |
| `created_at` | string ISO 8601 (UTC) | Sí | Momento en que se registró el turno | No | `2026-10-10T17:07:37.171542+00:00` |
