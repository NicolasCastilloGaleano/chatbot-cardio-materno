# ADR 0015: Persistencia SQLite con usuarios e hilos acotados por usuario

- **Estado:** Aceptado (2026-10-17)
- **Fecha:** 2026-10-17
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano)

## Contexto
Hoy no existe la noción de usuario:
- `ConversationService` atiende una sola sesión, y su único estado es `_active_thread_id`, en memoria.
- `JsonFileThreadRepository` guarda un archivo por hilo y no admite varios procesos ni escrituras concurrentes.

El ADR 0006 previó migrar a una base de datos "cambiando solo el adaptador" antes de un canal multiusuario.

En WhatsApp no hay sesiones: cada persona tiene un chat continuo en el que los hilos se abren y se cierran, siempre ligados a ella. El requisito principal es que **el agente siga recibiendo exactamente el mismo contexto** (prompt, JSON del hilo, últimos N mensajes, evidencia solo en la respuesta) y que nunca se mezclen personas.

## Decisión
1. **SQLite** (`sqlite3` de la biblioteca estándar, modo WAL) en `DATABASE_PATH` (por defecto `data/cardio_materno.db`). Esquema versionado con `PRAGMA user_version`. Sin dependencias nuevas.
2. **Modelo** (detalle en `docs/04-datos/modelo-datos.md`):
   - `users`: la persona, independiente del canal. Incluye `consent_status`, que por ahora es `pendiente`.
   - `channel_identities`: (`channel`, `channel_user_hash`) → `user_id`.
   - `threads` (+ `user_id`), `messages` y `alerts`: lo mismo que el JSON actual.
   - `inbound_events`: deduplicación y auditoría, **sin texto**.
   - `outbound_messages`: trazabilidad de lo enviado.
3. **Identidad seudonimizada:** se guarda `HMAC-SHA256(USER_ID_HASH_SECRET, wa_id)`, nunca el teléfono ni el nombre de perfil. El `wa_id` solo vive en memoria mientras se procesa el mensaje, para poder responder.
4. **Repositorio acotado por usuario:** un `ThreadRepository` que solo ve los hilos de un `user_id` y les asigna ese dueño al guardarlos. **El puerto `ThreadRepository` no cambia.**
5. **Un `ConversationService` por mensaje**, construido con ese repositorio y con el hilo abierto del usuario. El único cambio en el servicio es un parámetro opcional `active_thread_id` en el constructor. La consola y la web no lo usan y siguen igual.
6. **Un solo hilo abierto por usuario**, garantizado por un índice único parcial (`WHERE status = 'abierto'`).
7. **Cierre por inactividad:** una regla determinista (`THREAD_IDLE_TIMEOUT_HOURS`, 12 h por defecto) cierra el hilo abierto antes de procesar un mensaje si lleva más tiempo sin actividad. Para el agente equivale al "salir" de la consola. La decisión de continuar o abrir un hilo sigue siendo del análisis, como hoy (ADR 0006).
8. **La consola y la web siguen con JSON** en esta fase. El adaptador SQLite cumple el mismo contrato y se prueba con las mismas pruebas, así que migrarlas después solo cambia el *bootstrap*.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| PostgreSQL | Concurrencia real, listo para producción | Otro servicio que instalar y operar, y una dependencia (driver) nueva para un prototipo de un solo proceso |
| Seguir con JSON (una carpeta por usuario) | Sin cambios | Sin transacciones, sin consultas, sin deduplicación confiable |
| ORM (SQLAlchemy) | Migraciones y portabilidad | Dependencia nueva; el esquema es pequeño |
| Pasar `user_id` a `ConversationService.send` | Explícito | Cambia el núcleo del agente y el puerto; mayor riesgo de regresión |
| Guardar el teléfono cifrado | Permite mensajes proactivos | Más datos personales y gestión de llaves; no hace falta en esta fase |

## Consecuencias
- ✅ Se separan las personas sin tocar el agente, los prompts, los filtros ni el RAG.
- ✅ Transacciones, consultas por usuario y deduplicación persistente.
- ✅ Queda lista la base para Telegram (otra fila en `channel_identities`) y para el consentimiento (HU-01).
- ⚠️ SQLite admite un solo escritor a la vez. Es suficiente con la cola de un trabajador (ADR 0014); con varios procesos se reevaluará PostgreSQL.
- ⚠️ Sin el teléfono no se pueden enviar mensajes proactivos (B-016). Se decidirá cuando haga falta.
- ⚠️ Perder `USER_ID_HASH_SECRET` desliga a las personas de su historial: el secreto se respalda junto con la base de datos.
- Pendiente: política de retención y borrado por usuario (Ley 1581), y migrar la web de auditoría a SQLite con filtro por usuario.
