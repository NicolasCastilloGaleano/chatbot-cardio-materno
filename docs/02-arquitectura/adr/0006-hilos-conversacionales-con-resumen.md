# ADR 0006: Hilos conversacionales con resumen estructurado por el agente

- **Estado:** Aceptado
- **Fecha:** 2026-10-10
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano)

## Contexto
En la HU-00 el contexto era una lista de los últimos 20 mensajes, sin noción de tema. Esa lista crece y Ollama la recorta en silencio al superar `num_ctx`, además de mezclar consultas distintas. Se necesita un contexto acotado y una forma de agrupar los mensajes por caso, con trazabilidad.

## Decisión
1. **Hilo = una consulta o caso.** Cada hilo tiene un JSON con `id` (UUID), `domain` (`materno_infantil` / `cardiovascular` / `ninguno`), `summary`, `status` (`abierto` / `cerrado`) y marcas de tiempo. **Cada mensaje guarda su `thread_id`.**
2. **Respuesta estructurada del agente.** En **una sola llamada por turno**, el agente devuelve `{thread_action, domain, summary, reply}`. La salida se restringe con el parámetro `format` (JSON Schema) de Ollama y la aplicación la valida (`parse_agent_turn`).
3. **El agente decide la continuidad:** con `continuar` se actualizan el resumen y el dominio del hilo; con `nuevo` se cierra el hilo actual y se abre otro.
4. **Contexto acotado:** prompt de sistema + JSON del hilo actual + últimos `THREAD_CONTEXT_MESSAGES` mensajes del hilo (6 por defecto) + mensaje nuevo.
5. **Persistencia en archivos JSON** (`data/threads/<id>.json`, un archivo por hilo y escritura atómica) detrás del puerto `ThreadRepository`.
6. Cada sesión de consola empieza sin hilo activo; con `salir` se cierra el hilo activo.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Dos llamadas por turno (clasificar el hilo y luego responder) | Cada prompt es más simple y la clasificación es más precisa | El doble de latencia con un modelo de 24B |
| Detectar el cambio de tema con reglas o embeddings | Determinista | Más trabajo; las reglas de texto libre son frágiles |
| Ventana deslizante de mensajes (HU-00) | Simple | Contexto sin tema; recorte silencioso |
| SQLite desde ya | Concurrencia y consultas | Más trabajo; el JSON no se ve directamente en la demo |

## Consecuencias
- ✅ El contexto queda acotado y predecible, los mensajes son trazables por caso y el JSON se puede ver en la demo. Además, es la base para Telegram (un hilo activo por usuario) y para las métricas por consulta.
- ⚠️ La decisión de hilo y el resumen dependen del LLM (riesgo R-08). Es una decisión **no clínica**, así que no contradice el ADR 0004. Los mensajes originales se conservan completos para que las reglas de alarma futuras operen sobre el texto original.
- ⚠️ Los archivos JSON no soportan varios procesos a la vez. Antes del adaptador de Telegram se migrará a una base de datos cambiando solo `JsonFileThreadRepository`.
- Si la calidad de `thread_action` no es suficiente en las pruebas, se pasará a dos llamadas (primera alternativa).

## Actualización 2026-10-10: dos llamadas (ADR 0008)
- La respuesta estructurada se divide en **análisis** (`thread_action`, `domain`, `summary`, `reported_symptoms`) y **respuesta** (`reply`, `evidence_ids`). Era la alternativa "dos llamadas" de este ADR, y la motivó la integración del RAG.
- **Resumen:** lo escribe el análisis, antes de que exista la respuesta del turno. Cada respuesta queda completa en los mensajes recientes del turno siguiente y entra al resumen en ese turno. Excepción: la última respuesta de un hilo que se cierra no queda en el resumen (sí en `messages`). Si hace falta, se resolverá con un resumen de cierre.

## Actualización 2026-10-17: base de datos por usuario (ADR 0015)
- Se cumplió lo previsto en las consecuencias: `SqliteThreadRepository` implementa el mismo puerto, acotado a un usuario, y pasa las mismas pruebas de contrato que el repositorio JSON. La consola y la web siguen con JSON. El cierre por inactividad se agrega como regla determinista; la decisión `continuar`/`nuevo` sigue siendo del análisis.
