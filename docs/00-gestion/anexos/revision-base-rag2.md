# Revisión de la base RAG v2 frente a la v1

- **Fecha:** 2026-10-26
- **Autoría:** Claude Code (Opus 5.5), a pedido del equipo. Pendiente de revisión por el equipo.
- **Decisión que motivó:** revertir `main` al estado de la HU-10 (`91fe43a`) y poner en pausa el [plan de migración](../plan-migracion-rag2.md).

## 1. Conclusión

La base v2 (`RAG_2.xlsx`) **no es una base de conocimiento: es un guion de conversación**. Cada cuadro tiene 12 turnos de un caso inventado, y cada respuesta contesta el mensaje anterior de ese caso. Un buscador por similitud no puede seguir un guion. Por eso la migración necesitó una máquina de etapas (fase 3), y aun así el asistente mostró datos que la persona no había dado. La v1 (`knowledge/kb/entries.jsonl`), con registros generales por situación, encaja mejor con el diseño actual (consulta reformulada por el análisis → búsqueda → respuesta verificada).

## 2. Cifras (script de solo lectura sobre las dos bases)

| | v1 | v2 |
|---|---|---|
| Registros | 1.600 (16 categorías × 100) | 2.304 (192 cuadros × 12 etapas) |
| Preguntas que empiezan en minúscula | 0 % | 54 % |
| Preguntas con jerga o abreviaturas ("q", "taita", "bb") | 0 % | 11 % |
| Preguntas de menos de 8 palabras (dependen del turno anterior, p. ej., "¿qué hago ya?") | 0 % | 7 % |
| Respuestas que terminan en pregunta | 1 % | 100 % |
| Respuestas con cantidades o tiempos concretos ("tres horas", "seis semanas") | 3 % | 31 % |
| Respuestas que reutilizan detalles de su propio mensaje de ejemplo (medida aproximada) | — | ≈ 39 % |
| Respuestas que arrancan como continuación de otro turno | 0 | 171 |
| Fuente, validado por y fecha por registro | No (decisión `VALIDADA_PARA_PROTOTIPO`) | No (sin decisión, puerta P1) |

## 3. Problemas encontrados

1. **Respuestas atadas al caso de ejemplo.** En el cuadro `colico_lactante`, la verificación dice "tu bebé de mes y medio llora fuerte casi todas las noches en la misma franja…", y la de T3 responde a "mi hermana insiste en la aromática de manzanilla". Solo son correctas si la persona dijo exactamente eso. En el PC de pruebas (MIG-09 a MIG-11) aparecieron "seis semanas", "mal de ojo" y "lo revisaron y está sano" sin que la persona lo dijera.
2. **Se busca con un texto y se compara contra otro distinto.** El análisis convierte el mensaje de la persona en una consulta clara (`search_query`). El índice de la v2 se calcula con la pregunta coloquial y la respuesta personalizada (`KnowledgeEntry.embedding_text`), que traen detalles ajenos a la consulta ("la finca", "son las siete").
3. **La medición de MIG-08 no representa el uso real.** El 62 % de aciertos del cuadro en el primer resultado se midió buscando con las mismas preguntas coloquiales de la base, no con la consulta reformulada que usa el asistente. Aun así, falla 4 de cada 10 veces.
4. **Interacción con otras reglas.** Como todas las respuestas terminan en pregunta, la regla de respuesta a una pregunta pendiente (MIG-01) casi nunca permite el fuera de alcance. Además, los registros tan específicos fallan más en la verificación y se muestran más como texto literal (3 de 5 turnos en la prueba de MIG-11).
5. **Lenguaje diagnóstico.** La columna "Lectura clínica" está escrita en lenguaje de diagnóstico y no puede llegar ni a la persona ni al agente.

## 4. Lo que sí aporta la v2 (como insumo, no como índice)

- **Cubre vacíos de la v1.** Por ejemplo, la v1 no tiene registros sobre el cólico del lactante. Esos cuadros se pueden reescribir como registros generales al estilo de la v1, sin los datos del caso de ejemplo.
- **La columna "Preguntas" es un banco de mensajes coloquiales reales etiquetados.** Sirve para probar el prompt de análisis (normalización de la consulta) y el filtro 1 de alarmas.
- **Las "Señales de escalamiento" son candidatas para `examples` del catálogo de alarmas**, siempre con revisión clínica (AGENTS.md §4–§5).
- **El tono es más cercano** y da acciones concretas mientras la persona responde. Puede inspirar el prompt de respuesta.

## 5. Límites de esta revisión

- No se midió la recuperación con embeddings (Ollama corre en el PC de pruebas). Las cifras son de estilo y contenido.
- La decisión sobre la base (puertas P1 y P7 del plan) es del equipo y debe quedar en un ADR.
