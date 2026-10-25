# ADR 0010: Respuesta generativa verificada y abstención determinista

- **Estado:** Aceptado
- **Fecha:** 2026-10-11
- **Decisores:** Nicolas Castillo Galeano (eligió la respuesta generativa verificada con texto literal como respaldo)
- **Relacionado:** ADR 0004 (reglas deterministas), ADR 0008 (RAG y dos llamadas; este ADR reemplaza su punto sobre la abstención por prompt), riesgo R-10, B-018

## Contexto
El guion manual del 2026-10-11 en el PC de pruebas mostró que la regla "solo evidencia para afirmaciones de salud", aplicada solo con el prompt, no se cumple:

- **Respondía sin evidencia.** Con el RAG caído dijo "la presión alta puede dañar tus órganos". Con evidencia `insuficiente` recomendó "infusiones de jengibre o manzanilla".
- **Inventaba a partir de la evidencia.** Citó un registro *Indagar* que solo hace preguntas y agregó causas, cuidados y una lista de 13 alimentos. Además suavizó el aviso del registro: de "necesita atención obstétrica inmediata" pasó a "hables con tu médico". La cita (`evidence_ids`) no garantizaba nada.

Responder sin respaldo o deformar la evidencia es inaceptable en un servicio de salud.

## Decisión
1. **Abstención determinista:** si la búsqueda no es `suficiente` (insuficiente o RAG no disponible), **no se llama al LLM de respuesta**. Se muestra la plantilla `ABSTENTION_TEXT`. Si hay una alarma prioritaria, se muestra solo su mensaje fijo.
2. **Respuesta frase por frase:** la llamada de respuesta devuelve `{"sentences": [{"text", "evidence_id"}]}`. `evidence_id` se limita por `enum` a las etiquetas ofrecidas o a `"ninguna"` (`reply_prompt_v3.md`, `grounded_reply_schema`).
3. **Verificador determinista** (`domain/grounding.py`, sin dependencias nuevas). Una frase citada está respaldada si:
   - al menos `min_support` (0,6) de sus palabras con contenido aparecen en el registro citado (pregunta + respuesta). Se compara sin tildes, sin palabras vacías y por raíz simple de 5 letras;
   - **todos sus números** aparecen en el registro.
   Las palabras de remisión a urgencias y la línea 123 no cuentan en contra, porque remitir nunca minimiza el riesgo.
4. **Frases sin cita:** como máximo 2 y de 20 palabras o menos. Solo se aceptan si son una pregunta sin números, si usan solo palabras de cortesía, o si dicen que no pueden ayudar con algo usando solo palabras de cortesía o del mensaje de la persona. Las demás se descartan.
5. **Texto literal como respaldo:** si **una frase citada** no está respaldada, o no queda ninguna frase, se muestra el texto literal del registro principal (el primero citado o, si no hay citas, el mejor) con la plantilla "Según la información validada del proyecto: …". Así no se pierde ni se deforma un aviso.
6. **Traza:** `trace.grounding` registra las frases mostradas, el total, si se usó el texto literal y las frases descartadas. En la consola aparece la línea `[respaldo: …]`.
7. Los parámetros viven en `knowledge/evidence_policy.json` (`min_support`, `max_free_sentences`, `max_free_words`).

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Solo prompt (estado anterior) | Simple, natural | Falló en el guion: respuestas sin evidencia e inventadas |
| Extractiva pura (mostrar el registro tal cual) | Riesgo mínimo, sin llamada de respuesta | Se adapta menos a la pregunta; el usuario prefirió la verificada |
| Verificación con otro LLM (juez) | Entiende paráfrasis | No es determinista, es más lento y puede fallar igual |
| Verificación por embeddings | Tolera sinónimos | Umbral difícil de interpretar; no detecta un número cambiado |

## Consecuencias
- ✅ Ninguna afirmación de salud llega a la persona sin un registro que la respalde de forma verificable. La abstención ya no depende de que el modelo obedezca, y además ahorra entre 15 y 40 s en esos turnos.
- ✅ Calibración con las respuestas reales del guion: la respuesta de la presión pasa completa (0,75–1,00 por frase); en la de la acidez se rechazan justo las frases inventadas y el aviso suavizado.
- ⚠️ El verificador es léxico. Una paráfrasis con sinónimos puede rechazarse, y entonces se muestra el texto literal, que es seguro pero menos natural. La tasa de texto literal se mide en vivo (`tests/live/test_live_grounding.py`) y `min_support` se puede ajustar.
- ⚠️ Una pregunta sin cita podría insinuar algo ("¿sabías que…?"). Se acepta por ahora, con el límite de longitud y sin números; queda a vigilar en la traza.
- ⚠️ La base tiene vacíos (p. ej., alimentación con acidez o diabetes gestacional). Con esta decisión, esas preguntas reciben la abstención o un texto *Indagar*. Ampliar la base lo decide el equipo clínico (B-019).

## Actualización 2026-10-24: el texto literal sale del registro más parecido
- **Motivo:** en el PC de pruebas, "tengo acidez en el embarazo" recuperó un registro de acidez (similitud 0,60) y uno de preeclampsia (0,55). El agente redactó consejos que no estaban en ningún registro, citó el de preeclampsia y, al fallar la verificación, se mostró el literal de ese registro: "Busca valoración obstétrica inmediata y menciona… que tienes hipertensión". La persona no había dicho que tuviera hipertensión (causa U2 del [plan de migración](../../00-gestion/plan-migracion-rag2.md)).
- **Decisión:** el punto 5 cambia. El registro principal del texto literal es el de **mayor similitud** entre los ofrecidos; ante un empate, uno que haya citado el agente (`grounded_reply.py::main_label`). Si la redacción falló, su cita no es una señal confiable.
- **Consecuencia:** no cambia nada cuando la redacción se verifica. El texto literal sigue siendo un registro completo y validado; con la base v2 (un registro por turno) esta elección casi nunca se necesita.

## Actualización 2026-10-24: el texto literal se muestra sin prefijo
- **Motivo:** en la prueba del PC de pruebas, el prefijo "Según la información validada del proyecto: …" del punto 5 sonaba a sistema y no le aportaba nada a la persona. Además, la base v2 aún no tiene validación clínica (puerta P1 del plan de migración), así que "validada" podía inducir a error.
- **Decisión** (Santiago Silva): el texto literal se muestra solo con el contenido del registro (`LITERAL_TEMPLATE = "{answer}"`). Que la respuesta es literal sigue quedando en la traza (`grounding.literal`, "Texto literal: Sí" en el panel web y `[respaldo: … texto literal]` en la consola).

## Actualización 2026-10-24: la abstención pregunta (MIG-03)
- **Motivo:** la abstención era un texto fijo sin pregunta ni acción: un fallo de la búsqueda se convertía en el abandono de la persona (causa D3 del [plan de migración](../../00-gestion/plan-migracion-rag2.md)).
- **Decisión:** con búsqueda **insuficiente**, `ABSTENTION_TEXT` sigue sin llamar al LLM, pero termina con una pregunta fija que pide más detalles (qué siente, desde cuándo y a quién le pasa), para que el siguiente turno pueda encontrar evidencia. No dice "validada", igual que el texto literal. Con el RAG **no disponible** se usa `UNAVAILABLE_TEXT` (el texto anterior), porque pedir más detalles no ayudaría. Elige `grounded_reply.py::abstention_text`.

## Actualización 2026-10-24 (2): textos de abstención más claros
- **Motivo:** en la prueba del PC de pruebas, "información del proyecto" y "base de conocimiento del proyecto" sonaban raros para la persona, y el texto de RAG no disponible parecía decir que el tema no existía, cuando es un problema técnico del sistema.
- **Decisión** (Santiago Silva):
  - `ABSTENTION_TEXT`: "Todavía no tengo suficiente información para orientarte sobre lo que me cuentas. Mientras tanto, si tienes dudas, consúltalo con el personal de salud de tu EPS o centro de salud. ¿Me puedes contar con otras palabras qué sientes, desde cuándo y a quién le pasa?"
  - `UNAVAILABLE_TEXT`: "En este momento no puedo consultar la información para orientarte. Te recomiendo consultarlo con el personal de salud de tu EPS o centro de salud."

## Actualización 2026-10-24 (3): la remisión se verifica como cualquier frase (MIG-04)
- **Motivo:** el punto 3 eximía las palabras de remisión (`REFERRAL_WORDS`) y la línea 123 (`SAFE_NUMBERS`). Una frase hecha solo de esas palabras quedaba sin nada que comparar y **siempre** pasaba (causa U1 del [plan de migración](../../00-gestion/plan-migracion-rag2.md)): el agente podía mandar a urgencias sin respaldo, una de las causas de que el asistente escalara con demasiada facilidad.
- **Decisión:** se retira la excepción. Una frase de remisión se respalda como cualquier otra, y la línea 123 debe estar en el registro citado. Los avisos de urgencia que no vienen de un registro los compone la política de alarmas (ADR 0007), nunca el agente.
- **Consecuencia:** puede subir la tasa de texto literal cuando el agente agregue una remisión que el registro no dice. Se mide en el PC de pruebas con `tests/live/test_live_grounding.py`. Con la regla del registro más parecido (actualización anterior), ese literal sale del registro que mejor corresponde a la consulta.
