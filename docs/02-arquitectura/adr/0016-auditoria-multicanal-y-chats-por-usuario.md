# ADR 0016: Interfaz de auditoría multicanal; consola y web sobre SQLite con chats por usuario

- **Estado:** Aceptado (2026-10-18)
- **Fecha:** 2026-10-18
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano)
- **Modifica:** ADR 0013 (la web deja de tener una sola sesión), ADR 0006 y ADR 0015 (la consola y la web dejan el JSON)

## Contexto
La interfaz web (ADR 0013) audita los hilos guardados en archivos JSON y comparte una sola sesión por proceso. WhatsApp (ADR 0014) guarda en SQLite usuarios con un chat continuo y varios hilos (ADR 0015). Por eso la interfaz no puede auditar WhatsApp, y la consola y la web siguen otro modelo de datos.

El equipo necesita auditar todos los canales en un solo lugar: Telegram en el futuro, WhatsApp, consola y web. También quiere seguir conversando desde la interfaz con los chats de consola y web, sin poder escribir en los de WhatsApp o Telegram.

## Decisión
1. **Un solo modelo para todos los canales:** usuario → chat continuo → hilos → mensajes, en la base SQLite del ADR 0015.
   - **Consola:** cada arranque crea un usuario de canal `consola`. Ese chat no se retoma desde la consola; al cerrarla, se continúa en la web.
   - **Web:** "Nueva sesión" crea un usuario de canal `web`.
   - En los dos casos, la identidad de canal es un token aleatorio, sin datos personales.
2. **Escritura por canal, como regla de dominio:** `whatsapp`, `telegram` e `historico` son de solo lectura en la interfaz. El servidor rechaza los envíos a esos chats con 403; no basta con desactivar el campo de texto.
3. **Uso exclusivo de la consola:** mientras una consola está abierta, su chat queda en solo lectura en la web (`users.live_session_at`, esquema v2). Si la consola se cierra de golpe, la web permite liberarlo.
4. **Mismo agente y misma regla de inactividad:** todos los canales usan `UserConversations`, que cierra el hilo inactivo y crea un `ConversationService` con el repositorio acotado al usuario y su hilo abierto. Es lo que ya hacía WhatsApp, ahora compartido.
5. **Lectura para auditoría con un puerto propio (`ChatAudit`):**
   - lista de chats con filtro por canal;
   - páginas de mensajes por *keyset* sobre `messages.seq` (`before` para cargar hacia arriba, `after` para lo nuevo);
   - alertas de cada turno;
   - mensajes del canal todavía en proceso.
6. **Actualización automática por consulta periódica** (`WEB_POLL_SECONDS`, 3 s), sin WebSocket ni dependencias nuevas.
7. **Histórico:** un script importa una vez los JSON de `data/threads` a un chat `historico` de solo lectura. Es idempotente. `JsonFileThreadRepository` queda solo para esa importación y para las pruebas de contrato.
8. La interfaz sigue **solo en loopback** (ADR 0013).

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Mantener JSON para consola y web y leer además SQLite | Menos cambios | Dos modelos de datos y dos formas de auditar; la consola no se podría continuar en la web |
| Permitir escribir en chats de WhatsApp desde la web | Pruebas más rápidas | Mezclaría turnos que la persona no escribió con su conversación real |
| WebSocket o Server-Sent Events para lo nuevo | Actualización instantánea | Más complejidad; la consulta cada 3 s basta para uso local |
| Paginación por número de página (`offset`) | Simple | Repite o salta mensajes cuando llegan mensajes nuevos durante la auditoría |

## Consecuencias
- ✅ Una sola herramienta de auditoría para todos los canales, preparada para Telegram.
- ✅ La consola y la web prueban el mismo flujo por usuario que WhatsApp, incluida la inactividad.
- ✅ El agente, los prompts, los filtros y el RAG no cambian.
- ⚠️ La interfaz ahora muestra chats de WhatsApp: datos de salud de personas, por ahora solo números de prueba. Sigue sin autenticación y limitada a la propia máquina; antes de un piloto hacen falta autenticación y control de acceso.
- ⚠️ Los mensajes fuera de alcance no se guardan (HU-07), así que no aparecen en la auditoría.
- ⚠️ La web y WhatsApp pueden escribir en la misma base desde procesos distintos; SQLite en modo WAL con `busy_timeout` lo resuelve para el uso local.
