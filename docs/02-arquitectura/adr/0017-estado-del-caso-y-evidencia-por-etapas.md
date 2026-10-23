# ADR 0017: Estado del caso y evidencia por etapas

- **Estado:** Propuesto (pendiente de aprobación del equipo). Solo se activa con la base v2 ([ADR 0016](0016-base-de-conocimiento-v2-por-cuadros-y-etapas.md)); con la base v1 el asistente funciona como antes
- **Fecha:** 2026-10-22
- **Decisores:** equipo del proyecto (pendiente). La IA propone; el equipo decide (AGENTS.md §5)
- **Relacionado:** ADR 0004 (reglas deterministas), ADR 0006 (hilos), ADR 0008 (RAG), ADR 0010 (respuesta verificada), ADR 0016 (base v2), [plan de migración](../../00-gestion/plan-migracion-rag2.md) (MIG-09 a MIG-13)

## Contexto
El asistente no indagaba: no guardaba en qué punto del caso iba la conversación, la evidencia se elegía solo por similitud y una respuesta corta ("sí, desde ayer") casi nunca superaba el umbral (causas I1, I4 y D4 del plan). La base v2 trae, para cada cuadro, un registro por etapa (indagar en tres niveles, verificar, orientar, remitir, acompañar). Con ella, elegir el registro de un turno deja de ser un problema de similitud y pasa a ser un problema de **estado**.

El anexo de correcciones proponía tres agentes de LLM en paralelo y un orquestador. Con una GPU de 8 GB, Ollama atiende una solicitud a la vez y las llamadas se serializan: la latencia del análisis se multiplicaría (ADR 0011). Se buscó una solución determinista y en CPU.

## Decisión
1. **Estado del caso** (`domain/case_state.py`): `CaseState {motivo, etapa actual, etapas vistas}`. **No tiene almacenamiento propio:** viaja en la traza de cada respuesta del asistente (`case_motive`, `case_stage`, `case_visited`) y se recupera de los mensajes recientes del hilo (`application/case_flow.py::case_from_recent`). Así no cambian los esquemas de JSON ni de SQLite, ni el contrato de `ThreadRepository`.
2. **Identificación del cuadro por recuperación** (sin LLM extra): si el hilo no tiene cuadro o el análisis marca un tema nuevo, se busca en **toda la base, en los dos dominios**, con el umbral de la política; el cuadro es el del mejor registro. Mientras el análisis diga "continuar", el cuadro se mantiene.
3. **Reglas de etapas** (`plan_stages`, deterministas):
   - **Indagación primero:** T1 → T2 → T3 → verificación del cuadro. En cada turno se ofrece la siguiente o una etapa de **intención explícita** (qué hago ya, ya me atendieron, estoy esperando, tengo miedo), que se elige por similitud dentro del cuadro.
   - **Transición:** después de verificar el cuadro, se muestra la etapa de su **ruta base** (autocuidado → qué hacer ahora; consulta prioritaria → pedir la cita; urgencias → cómo trasladarse). Es contenido validado de la base, no decisión del LLM (ADR 0004).
   - **Después:** cualquier etapa que no sea de indagación, según lo que pregunte la persona.
4. **Selección dentro del cuadro sin umbral** (`EvidenceQuery.anchored`): con el cuadro identificado, la similitud solo ordena las etapas permitidas, así que una respuesta corta también recibe su registro.
5. **Un registro por turno** (`case_top_k` = 1 en la política): cada registro v2 hace una sola cosa y la respuesta no mezcla etapas.
6. **Un solo embedding por turno:** el buscador reutiliza el vector si el texto se repite (identificar y elegir usan el mismo).
7. **Prompt de respuesta v4:** en las etapas de indagación, hacer las preguntas del registro; terminar con su pregunta final; no agregar remisiones que el registro no diga.
8. **Auditor de salida determinista** (`application/output_audit.py`): si la respuesta verificada no termina en pregunta, se le agrega la pregunta final del registro que la respalda (texto del registro, así que no agrega afirmaciones sin respaldo).
9. Las **alarmas deterministas** se evalúan antes, como siempre, y tienen prioridad: estas reglas nunca rebajan una alarma.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Tres agentes de LLM en paralelo (anexo, #17 y #18) | Redundancia | En 8 GB se serializan; más latencia y más llamadas que verificar |
| `CaseState` como columna del hilo (JSON y SQLite) | Explícito | Cambia esquemas, migración de SQLite y el contrato del repositorio |
| Clasificar el cuadro con el LLM (lista cerrada de 192 motivos) | Entiende paráfrasis | Prompt enorme para un modelo local; otra llamada |
| Elegir la etapa solo por similitud | Simple | El primer turno podía ser una remisión; las respuestas cortas no superan el umbral |

## Consecuencias
- ✅ El asistente indaga antes de orientar y nunca remite en el primer turno por similitud (solo si el registro T1 del cuadro lo dice o si salta una alarma).
- ✅ Las respuestas cortas dentro de un caso reciben su registro, sin abstención.
- ✅ Sin llamadas nuevas al LLM ni cambios de esquema; la base v1 funciona igual.
- ⚠️ La identificación del cuadro depende de la similitud del primer mensaje: un cuadro equivocado arrastra el caso hasta que el análisis marque un tema nuevo. Se mide con `scripts/evaluate_kb_v2.py recuperacion`.
- ⚠️ La detección de intención explícita es por similitud dentro del cuadro: puede saltarse preguntas o no detectar un "¿qué hago?". Se mide en el guion del PC de pruebas.
- ⚠️ El estado se lee de los últimos mensajes del hilo (`CONTEXT_MESSAGES`): si se reduce mucho esa ventana, se puede perder el estado.
- ⏳ Pendiente: aprobación de este ADR y de la base v2 (P1/P7), recalibración del umbral y guion en el PC de pruebas.
