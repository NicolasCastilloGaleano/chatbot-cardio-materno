# ADR 0018: Estado del caso y evidencia por etapas

- **Estado:** Propuesto (pendiente de aprobación del equipo). Solo tiene efecto con la base v2 ([ADR 0017](0017-base-de-conocimiento-v2-por-cuadros-y-etapas.md)); con la base v1 el asistente funciona como antes
- **Fecha:** 2026-10-25
- **Decisores:** equipo del proyecto (pendiente). La IA propone; el equipo decide (AGENTS.md §5)
- **Relacionado:** ADR 0004 (reglas deterministas), ADR 0006 (hilos), ADR 0008 (RAG), ADR 0010 (respuesta verificada), ADR 0015 (SQLite), ADR 0017 (base v2), [plan de migración](../../00-gestion/plan-migracion-rag2.md) (MIG-09 a MIG-13)

## Contexto
El asistente no guarda en qué punto del caso va la conversación: la evidencia se elige solo por similitud. Con la base v2, cada cuadro tiene un registro por etapa (indagar en tres niveles, verificar, orientar, remitir, acompañar), así que elegir el registro de un turno es un problema de **estado**, no de similitud.

Las mediciones de la fase 2 lo confirman (2026-10-25):
- En la prueba de MIG-07, el primer turno recuperó registros de etapas posteriores y el agente repitió datos que la persona no dio ("en la cocina", "que la acidez haya cedido"). La verificación de respaldo no lo detecta, porque esos datos están en el registro citado.
- Con `scripts/evaluate_kb_v2.py recuperacion` (MIG-08), el mensaje que abre un caso trae el cuadro correcto primero en el 62 % y entre los tres primeros en el 84 %, y en el 20 % el primer resultado es de una etapa de orientación, remisión o acompañamiento (20 de 384, `traslado_urgencias`).

El anexo de correcciones proponía tres agentes de LLM en paralelo. Con una GPU de 8 GB, Ollama atiende una solicitud a la vez y las llamadas se serializan (ADR 0011), así que se busca una solución determinista y en CPU.

## Decisión
1. **Estado del caso** (`domain/case_state.py`, MIG-09): `CaseState {motivo, etapa actual, etapas vistas}`, que avanza con `advance` (si cambia el cuadro, el caso empieza de nuevo).
2. **Sin almacenamiento propio:** el estado viaja en la traza de cada respuesta del asistente (`case_motive`, `case_stage`, `case_visited`; clave `case` en el JSON de la traza) y se recupera de los mensajes recientes del hilo (`application/case_flow.py::case_from_recent`). No cambian los esquemas de JSON ni de SQLite ni el contrato de `ThreadRepository`; las trazas anteriores se leen sin estado. Si el análisis marca un tema nuevo, el caso empieza de nuevo.
3. **Primero se observa (MIG-09):** el estado se toma del registro principal que respalda la respuesta (el primero citado, o el del texto literal), sin cambiar todavía cómo se busca la evidencia. Así se puede revisar en el panel de auditoría y en las líneas de depuración antes de que decida algo.
4. **Identificar el cuadro y mantenerlo (MIG-10, `application/case_flow.py::CaseFlow`):**
   - Si el hilo no tiene cuadro, o el análisis marca un tema nuevo, se busca en **toda la base, en los dos dominios** (el dominio del análisis ya no confina la búsqueda), con el umbral de la política. El cuadro es el del mejor registro.
   - Mientras el análisis diga "continuar", el cuadro se mantiene y se busca **solo dentro de él** (`EvidenceQuery.motives`), entre las etapas que aún no se mostraron (`pending_stages`, `EvidenceQuery.stages`), **sin umbral** (`anchored`): una respuesta corta también recibe su registro y nunca se repite el anterior.
   - **Un registro por turno** (`case_top_k` = 1, `RAG_CASE_TOP_K`), para que la respuesta no mezcle cuadros ni etapas.
   - Un solo embedding por turno: el buscador reutiliza el vector si el texto se repite.
   - Desde aquí el estado sale de esta selección (ya no del registro citado, como en MIG-09).
5. *(Pasos siguientes, se documentarán al implementarse)*:
   - **MIG-11:** reglas deterministas de etapas: indagación primero (T1 → T2 → T3 → verificación), saltos solo por intención explícita, y después de verificar, la etapa de la ruta base del cuadro.
   - **MIG-12:** prompt de respuesta v4 y auditor de la pregunta final.
   - **MIG-13:** ruta de atención desde la ruta base del cuadro.
6. Las **alarmas deterministas** se evalúan antes, como siempre, y tienen prioridad: el estado del caso nunca rebaja una alarma.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| `CaseState` como columna del hilo (JSON y SQLite) | Explícito y fácil de consultar | Cambia esquemas, exige migrar SQLite y cambia el contrato del repositorio |
| Tres agentes de LLM en paralelo (anexo, #17 y #18) | Redundancia | En 8 GB se serializan: más latencia y más llamadas que verificar |
| Clasificar el cuadro con el LLM (lista cerrada de 192 motivos) | Entiende paráfrasis | Prompt enorme para un modelo local y otra llamada |
| Activar de una vez el flujo por etapas | Un solo cambio | Más difícil de revisar y de probar paso a paso |

## Consecuencias
- ✅ Cada respuesta con evidencia de la base v2 deja registrado su cuadro, su etapa y las etapas vistas, en los dos repositorios, sin cambios de esquema.
- ✅ La base v1 y las trazas anteriores funcionan igual (sin estado).
- ⚠️ El estado se lee de los últimos mensajes del hilo (`CONTEXT_MESSAGES`, 6): si se reduce mucho esa ventana o hay muchos turnos sin evidencia seguidos, se pierde.
- ✅ Desde MIG-10 una respuesta no repite el registro anterior ni mezcla cuadros, y una respuesta corta dentro del caso no se abstiene.
- ⚠️ El cuadro se identifica con el mejor registro del primer mensaje (62 % de acierto en la línea base de MIG-08): un cuadro equivocado arrastra el caso hasta que el análisis marque un tema nuevo. La votación entre los primeros resultados que propone el plan queda por medir.
- ⚠️ Hasta MIG-11 las etapas no tienen orden: dentro del cuadro gana la más parecida que no se haya mostrado, así que todavía puede saltar a orientar o remitir y repetir datos que la persona no dio.
- ⏳ Pendiente: aprobación de este ADR y de la base v2 (P1 y P7), y verificar en el PC de pruebas que el estado se registra bien.
