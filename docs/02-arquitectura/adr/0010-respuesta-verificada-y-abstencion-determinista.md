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

## Actualización 2026-10-26: correcciones de abstención y respaldo (rama `fix/alcance-y-respaldo`)
- **Abstención que pregunta:** `ABSTENTION_TEXT` conserva el aviso de consultar al personal de salud y termina pidiendo más detalles ("qué sientes, desde cuándo y a quién le pasa"). Así la persona puede reformular y el sistema puede volver a buscar. Sigue sin llamar al LLM y sin afirmaciones de salud.
- **RAG no disponible:** tiene un mensaje propio (`UNAVAILABLE_TEXT`), que no pide detalles porque no ayudarían. `abstention_text(status)` elige el mensaje según el resultado de la búsqueda.
- **Las remisiones también necesitan respaldo:** se quitan `REFERRAL_WORDS` y `SAFE_NUMBERS` de `domain/grounding.py`. Antes, una frase como "acude de inmediato a urgencias o llama al 123" pasaba siempre la verificación, aunque el registro citado no lo dijera, y el agente podía remitir sin respaldo. Los avisos de urgencia de las alarmas no se afectan, porque los compone `compose_reply` y no el agente. Riesgo: más respuestas con texto literal; se mide antes y después con `pytest -m live` (`test_live_grounding.py`).
- **Texto literal del registro más parecido:** cuando la redacción falla, la cita del agente no es confiable. `main_label` elige el registro de mayor similitud y, si empatan, el citado. Caso real (2026-10-24): "tengo acidez en el embarazo" citó un registro de preeclampsia (0,55) habiendo uno de acidez (0,60), y el literal remitió a urgencias. Se mantiene el prefijo "Según la información validada del proyecto:".
