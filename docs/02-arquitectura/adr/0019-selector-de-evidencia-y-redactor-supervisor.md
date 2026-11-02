# ADR 0019: Selector de evidencia y redactor supervisor

- **Estado:** Propuesto (2026-11-01), pendiente de revisión del equipo. Los puntos de la sección "Puntos por decidir" se cierran antes de implementar el paso que los usa
- **Fecha:** 2026-11-01
- **Decisores:** equipo del proyecto (Nicolas Castillo Galeano; equipo clínico para los avisos de atención). La IA propone; el equipo decide (AGENTS.md §5)
- **Modifica:** ADR 0008 (una llamada más al modelo de respuesta), ADR 0010 (de dónde sale el texto literal) y ADR 0017 (un modo nuevo y un veredicto que puede cambiar el modo del turno)
- **Historia:** HU-13 (B-031)

## Contexto
Con la HU-11 cerrada, el mayor problema que queda es la **pertinencia**: las respuestas están respaldadas, pero no siempre sirven (aorta para el dolor de brazo, sudor frío que nadie mencionó, frases que no aplican). La verificación del ADR 0010 comprueba que una frase esté en el registro, no que le sirva a la persona. La actualización de B-028 ya lo señaló: el criterio del literal es léxico y el prompt v4 pide elegir y redactar en la misma llamada.

El líder del proyecto pidió que la respuesta sea útil y clara, que atienda la consulta, que siempre responda específicamente a la pregunta y que sea aplicable en el momento, no solo pedir asistencia médica.

Hoy `_draft` hace dos trabajos en una llamada: elegir qué usar y redactar. Decisión del usuario (2026-10-31): **una tarea por agente, sin duplicar trabajo**. Un agente decide evidencias y frases; otro toma eso y genera la respuesta. No hay un revisor posterior que repita el trabajo.

## Decisión
Quien coordina es **el código determinista**, no un LLM. Los agentes son especialistas. Las alarmas, el riesgo y las rutas siguen siendo reglas (ADR 0004), y ninguna afirmación de salud se muestra sin respaldo verificable (ADR 0010).

1. **Numerar frases (determinista, `application/evidence_selection.py`).** Cada registro *Solucionar* ofrecido se parte con `split_sentences` en frases con id (`E2.3`). Las preguntas no se ofrecen (`without_questions`). La evidencia nunca llega a la llamada de análisis (ADR 0008).
2. **Agente selector** (`evidence_selection_prompt_v1.md`, modelo del análisis por defecto; ver "Mediciones del selector"). Recibe la pregunta, el CASO y las frases numeradas. Devuelve:
   - `verdict`: `responde`, `parcial` o `no_responde`;
   - `selected`: ids en orden de importancia, limitados por `enum` en el esquema.

   Criterio: solo lo que responde a lo que la persona pregunta y aplica a su situación; primero lo que puede hacer ahora. Como elige ids, **no puede inventar texto**.
3. **Refuerzo determinista.** Se agregan las frases con aviso de atención de los registros elegidos (`has_attention_notice`), para no perder una remisión. Ver el punto 1 por decidir.
4. **Agente redactor supervisor** (`reply_prompt_v5.md`). Recibe solo las frases seleccionadas y genera la respuesta: primero la respuesta directa a la pregunta, luego lo aplicable en el momento y la remisión al final, en lenguaje claro. No decide qué evidencia usar. Sale frase por frase con cita.
5. **Verificación** (`compose_grounded_reply`, sin cambiar la regla), contra las frases seleccionadas.
6. **Si falla la verificación:** texto literal de las frases seleccionadas, que ya son pertinentes. En este flujo reemplaza a la selección léxica de `pertinent_sentences`, que queda para el modo `apagado`.
7. **El veredicto decide con una regla, no con el LLM** (tabla del punto 2 por decidir).
8. **Modo responder e indagar** (`TurnMode.ANSWER_AND_INQUIRE`): la respuesta verificada y **una** pregunta para afinar el caso (`INQUIRY_MAX_QUESTIONS_WITH_ANSWER`, 1). Aplica cuando hay un registro *Solucionar* sobre 0,50, la evidencia no es clara o el selector dijo `parcial`, la persona reporta síntomas sin pedido directo y quedan turnos de indagación. Cuenta como turno de indagación. Se entrega en un paso aparte, porque cambia la regla de la HU-11: hoy indagar no muestra evidencia.
9. **Activación gradual** con `EVIDENCE_SELECTION_MODE`:
   - `apagado`: el flujo actual, sin llamada nueva;
   - `observar` (por defecto en la primera entrega): el selector corre y su resultado solo va a la traza; el turno se resuelve como hoy;
   - `activo`: selector y redactor deciden la respuesta.
10. **Si falla la llamada del selector:** se usa el flujo actual, sin error para la persona. La traza lo registra.
11. **Auditoría:** `SelectionTrace` guarda el veredicto, los ids, las frases ofrecidas y seleccionadas, los avisos agregados y omitidos y si se aplicó (`applied`). Se ve en la web, la consola y `scripts/export_traces.py`. Sin almacenamiento nuevo: viaja en la traza, como en el ADR 0017.

### Cuándo corre el selector
Solo en los turnos que van a mostrar evidencia y tienen al menos un registro *Solucionar*. No corre con una urgencia inmediata nueva, ni en turnos conversacionales, fuera de alcance, de indagación, de abstención o de cierre. Sí corre con una alarma prioritaria nueva y con una urgencia recordada (B-030), con el contexto URGENCIA EN CURSO.

### Entrega por pasos
| Paso | Qué entrega | Cambia lo que ve la persona |
|---|---|---|
| 1.1 | Numeración, selector en `observar`, traza y auditoría. El flujo con evidencia sale a un colaborador, para no seguir creciendo `conversation_service.py` | No |
| 1.2 | Redactor con `reply_prompt_v5.md`, literal de las frases seleccionadas y veredictos en `activo` | Sí, solo con `activo` |
| 1.3 | Responder e indagar | Sí, solo con `activo` |

Cada paso se verifica en el PC antes del siguiente. Si el selector no elige bien en `observar`, no se construye el redactor. El resultado se revisa con el líder del proyecto antes de seguir con las demás etapas.

## Guion en modo activo (2026-11-02)
| Caso | Resultado |
|---|---|
| Sangrado, 3 veces | ✅ Recordatorio y traslado, 3/3 frases respaldadas, sin convulsión. Ojo: en estas corridas la búsqueda no trajo ese registro, así que lo que lo descarta sigue probado solo una vez en la web y con evidencia fija |
| Ardor | ✅ Dos preguntas para distinguir (turno 1 de indagación), sin urgencias ni sudor frío |
| Presión alta | ✅ Solo el mensaje fijo |
| Comida | ⚠️ DASH correcto, pero el redactor usó 1 de 4 frases visibles. Se ajustó `reply_prompt_v5.md` para que las use |
| Brazo y pecho pesado | ✅ Sin cambios |

Ninguna respuesta cayó en texto literal. Un turno con evidencia tarda de 95 a 105 s, y la selección, de 18 a 33 s. El redactor puede omitir un aviso reforzado: en una corrida del sangrado dejó fuera "sangrado abundante…", que la persona no dijo. Se debe revisar con el punto 1.

## Propuesta: orientación en el primer aviso de una urgencia (B-034, por decidir)
**Pedido del usuario (2026-11-02):** en una emergencia, la persona no debería tener que preguntar "¿qué hago mientras llego?": la primera respuesta debe traer algo que pueda hacer en el momento, y la solución debe ser general, sin textos fijos por alarma.

Hoy, una urgencia inmediata solo muestra el mensaje fijo (ADR 0007), y el acompañamiento (B-030) solo existe cuando la persona vuelve a escribir.

**Solución general propuesta:** reutilizar el acompañamiento para el primer aviso. El mensaje fijo sigue siendo determinista y sale primero; el código busca, selecciona y redacta con URGENCIA EN CURSO, sin ramas por alarma.

| Opción | Ventaja | Costo |
|---|---|---|
| **Dos mensajes (recomendada):** el mensaje fijo sale de inmediato y la orientación llega sola después | No retrasa el aviso | La web, la consola y WhatsApp deben mostrar un segundo mensaje sin que la persona escriba |
| Un solo mensaje | Lo pedido literalmente | La persona esperaría decenas de segundos antes de ver "ve a urgencias" |

**Límites:**
- Solo se puede decir lo que está en la base (ADR 0010). Si un registro no trae qué hacer en el momento, ningún agente lo inventa: eso va al equipo clínico (B-032).
- Con filtro 1, hoy no hay análisis. La búsqueda y el CASO saldrían del mensaje de la persona, o habría que correr el análisis para esa segunda parte.
- Modifica el ADR 0007 (`urgencia_inmediata` sin respuesta del LLM), por lo que es una decisión del equipo clínico (P4).

## Paso 1.2 (2026-11-02)
- **Aprobados por el usuario (Santiago Silva):** el paso 1.1 con su resultado en la web y la regla de `en_parte`. Pendiente la revisión con el líder.
- **Implementado detrás de `EVIDENCE_SELECTION_MODE=activo`:** frases visibles (`visible_ids`), redactor (`reply_prompt_v5.md`), verificación contra las frases visibles sin la pregunta del registro, literal de esas frases (`with_selected_literal`) y decisión final (`mode_without_answer`). La traza guarda el modo que eligió la regla (`rule_mode`).
- **Visibles:** las frases de los registros `si`. Las de un registro `en_parte`, solo con una urgencia en curso. Un registro sin evaluación no se muestra.
- **Regla provisional de los avisos (punto 1, sigue abierto):** solo se refuerzan los de los registros `si`. Por eso `observar` sigue siendo el valor por defecto: `activo` no pasa a ser el valor por defecto ni se fusiona hasta que decida el equipo clínico.
- **Colaborador:** el flujo con frases seleccionadas sigue en `conversation_service.py`, con sus reglas en funciones puras de `evidence_selection.py`. No se extrajo más, para no mezclar esa reorganización con este cambio.

## Decisiones y avance (2026-11-01)
- **Puntos 2 a 5:** propuestas aprobadas por el usuario (Santiago Silva). Pendiente la revisión con el líder del proyecto.
- **Punto 1:** sigue abierto. Lo decide el equipo clínico con lo medido en `observar`.
- **Paso 1.1, implementado** en `feat/hu-13-selector-redactor`: numeración, selector y su prompt, frases de contexto, revisión de avisos, traza y auditoría. `EVIDENCE_SELECTION_MODE` admite por ahora `apagado` y `observar`; `activo` se rechaza al arrancar hasta el paso 1.2. El colaborador extraído es `EvidenceSelector`: el resto del flujo con evidencia sale del servicio en el paso 1.2, que es el que lo cambia. Falta la verificación en el PC ([guion](../../08-despliegue/prueba-selector-observar.md)).

## Primera prueba del paso 1.1 (2026-11-01): no aprobada
| Caso | Veredicto | Resultado |
|---|---|---|
| Sangrado | `responde` | **No probó la condición:** la búsqueda solo trajo el registro de sangrado, sin el de convulsión. La falla de la línea base es intermitente. Además, eligió "sangrado abundante junto con dolor abdominal", que la persona no dijo |
| Ardor | `responde` | Eligió "sudor frío", "este cambio" y "explica cuándo comenzó" (sin destinatario). El aviso de urgencias quedaría agregado. El único registro *Solucionar* trata de un dolor con sudor frío: debía ser `parcial` o `no_responde` |
| Presión alta | `responde` | Eligió "esa presión es marcadamente elevada", de un registro de 190/125, sin que la persona diera cifras. Sí dejó por fuera el dolor en el pecho |
| Comida (DASH) | — | No se corrió |
| Brazo y pecho pesado | No corre | Correcto |

Las tres veces dijo `responde`, y no distinguió el tema de la situación. Se ajustó el prompt (comparar el registro con el caso; frases que suponen datos no dichos o no se entienden solas; veredicto exigente), se agregaron `esa`, `ese`, `esas` y `esos` a los marcadores de continuación y se creó `tests/live/test_live_selection.py`, con la evidencia fija para no depender de la búsqueda. **Límite:** muchas frases mezclan una parte útil con un dato no dicho, y no se pueden cortar sin cambiar la base; eso va a los vacíos del contenido (B-032).

## Prueba con evidencia fija (2026-11-01): 2 de 4, una sola corrida
| Caso | Veredicto | Resultado |
|---|---|---|
| Sangrado con un registro de convulsión | `responde` | ✅ Eligió solo frases del sangrado, sin "sangrado abundante" |
| Comida con el registro de DASH | `responde` | ✅ Empezó por DASH |
| Ardor con un registro de sudor frío | `responde` | ❌ 5 frases, incluidas "busca atención de urgencias" y "sudor frío" |
| Presión alta sin cifras con un registro de 190/125 | `responde` | ❌ 5 frases, incluida "marcadamente elevada" (y la anterior, por contexto) |

**Lectura:** el selector distingue entre registros de temas distintos, pero no rechaza un registro parecido cuando es el único ofrecido: llena el máximo de frases y dice `responde`. Son las situaciones que más necesitan `parcial` o `no_responde`. Una corrida no demuestra que el caso del sangrado sea estable. Siguen, sin cambiar código, tres mediciones: repetir la prueba, probar el modelo del análisis y bajar el máximo de frases. Si no bastan, se propone que el selector primero declare, por registro, qué datos supone que la persona no dio.

## Mediciones del selector (2026-11-01)
| Medición | Sangrado | Ardor | Presión | DASH |
|---|---|---|---|---|
| `qwen3:8b`, 5 corridas | ✅ 5/5 | ❌ 0/5 | ❌ 0/5 | ✅ 5/5 |
| `mistral-small3.1:24b`, 1 corrida | ✅ `no_responde` | ✅ `no_responde` | ✅ `parcial`, 1 frase | ✅ `responde` |

- **El modelo es lo que marca la diferencia:** es la primera vez que aparecen `parcial` y `no_responde`.
- **La medición con 3 frases no fue válida:** la prueba tenía fijo el máximo en 5 e ignoró la variable. Se corrigió para usar la política.
- **Exceso de rigor en el sangrado:** con mistral no elige nada, porque el registro habla de un sangrado abundante. Es seguro (queda el recordatorio), pero pierde "pide ayuda para el traslado". Hay que revisar el prompt para ese caso.
- **Costo:** 171,6 s para 4 llamadas, con carga del modelo incluida; hace falta medir el tiempo por turno. Como el análisis ya usa ese modelo, el selector iría justo después sin otro cambio de modelo.
- **Decisión (2026-11-01, Santiago Silva; pendiente de la revisión con el líder):** el selector usa por defecto el modelo y la configuración del análisis. `OLLAMA_SELECTION_MODEL` permite indicar otro, con sus `OLLAMA_SELECTION_*`. Reemplaza al modelo de respuesta en la decisión 2. Si el selector usa el mismo adaptador del análisis, Ollama no recarga el modelo entre las dos llamadas.
- **Ajuste del prompt:** con URGENCIA EN CURSO, si el registro es de esa misma urgencia, se eligen las acciones generales aunque describa un caso más grave. La prueba en vivo exige que en el sangrado salga el traslado.

## Cinco corridas con el modelo del análisis (2026-11-01)
| Caso | Resultado | Lectura |
|---|---|---|
| Sangrado con convulsión | ❌ 5/5 `no_responde` | Nunca eligió la convulsión, pero tampoco el traslado. Seguro, pero no ayuda |
| Ardor | ✅ 5/5 `no_responde` | Corregido |
| Presión alta | ❌ 4 veces `parcial` con "marcadamente elevada"; 1 fallo de la llamada, sin causa registrada | Sigue tomando un registro de 190/125 |
| DASH | ✅ 5/5 | Estable |

Cada corrida de 4 llamadas tardó 29 a 39 s, carga del modelo incluida. Todas las 35 pruebas en vivo anteriores siguieron pasando con `qwen3:8b` y el selector observando.

**Ajuste:** las frases con demostrativo al inicio son 64 de 4.557 (1,4 %) y casi todas dependen de la frase anterior ("Estas medidas…"), así que no se creó una regla para excluirlas: `este`, `esta`, `estos` y `estas` pasan a ser marcadores de continuación. El selector ahora evalúa cada registro antes de elegir: `records` con `fit` (`si`, `en_parte`, `no`) y `unsaid` (datos que supone y la persona no dio). El código descarta las frases de los registros con `fit` = `no`. Con URGENCIA EN CURSO, un registro de esa misma urgencia no puede ser `no`. La traza guarda la evaluación y la causa de los fallos.

## Cinco corridas con evaluación de registros (2026-11-02)
| Caso | Evaluación | Resultado |
|---|---|---|
| Sangrado con convulsión | E1 `no` (convulsión), E2 `no` (sangrado abundante, dolor, 32 semanas) | ❌ 5/5 `no_responde`: seguro, sin el traslado. Marcó `no` el registro de la misma urgencia, pese al prompt |
| Ardor | `no` (sudor frío) | ✅ 5/5 |
| Presión alta | `en_parte` (cifra de 190/125) | ❌ 5/5: detecta el dato, pero elige "marcadamente elevada" |
| DASH | `si` | ✅ 5/5 |

Sin fallos de llamada en 20 llamadas. Cada corrida tardó de 61 a 72 s, carga incluida: la evaluación casi dobla el tiempo de la corrida anterior.

**Lectura:** `unsaid` identifica bien los datos no dichos y es estable. Las dos fallas vienen de pruebas con la evidencia más desfavorable (un registro específico, sin alternativa). No se sigue afinando el prompt con ellas: la decisión se toma con el guion en la web, con la evidencia que trae la búsqueda real. Las dos pruebas en vivo siguen en rojo a propósito hasta entonces.

## Guion en la web con la búsqueda real (2026-11-02)
| Caso | Respuesta mostrada (sin el selector) | Evaluación | Lo que habría elegido |
|---|---|---|---|
| Sangrado | **Instrucciones de una convulsión** (4/4 frases respaldadas) | Convulsión `no`; sangrado `en_parte` | `parcial`: solo "Pide ayuda para el traslado…" ✅ |
| Ardor | Urgencias y sudor frío, literal | `no` (sudor frío) | `no_responde` ✅ |
| Presión alta | Frases sobre la molestia en el pecho | `en_parte` (190/125): único registro *Solucionar* | `parcial`: incluye "marcadamente elevada" ❌ |
| Comida | Sobre la alimentación | E3 `si`, E2 `en_parte`, E4 `no` | `parcial`: 4 frases de DASH ✅ (debió ser `responde`) |

Una sola corrida. La convulsión volvió a salir en `main`: es la segunda vez en tres corridas de la web, y aquí el selector la descartó con la evidencia real.

**Tiempo:** la selección tardó de 18,1 a 32,8 s (leer 5 a 7 s; generar 12 a 26 s), más que lo estimado con las pruebas fijas. Un turno con evidencia pasa de unos 72 s a unos 97 s.

**Propuesta para el paso 1.2 (por aprobar):** el veredicto `parcial` no basta para mostrar un registro `en_parte`. Se muestran las frases de los registros `si`. Las de un registro `en_parte` solo se muestran con una urgencia en curso; en los demás casos, ese registro cuenta como `no_responde` y sigue la tabla del punto 2 (indagar, o solo el mensaje fijo de una alarma). Con esta regla, los cuatro casos quedan bien: traslado, indagar, solo el mensaje fijo y DASH.

## Línea base (2026-11-01, `main` en `79fa39a`)
Seis casos en el PC de pruebas, antes de cualquier cambio:

| Caso | Qué pasó | ¿Corre el selector? | Qué debe mejorar |
|---|---|---|---|
| "me duele el brazo" | Indaga: una pregunta. Sin registro que oriente | No | Nada: no se muestra evidencia |
| "tengo ardor en el pecho después de comer" | Literal de un registro de dolor torácico (0,53): "No esperes: busca atención de urgencias inmediatamente" y "sudor frío", que la persona no mencionó | Sí | Responder sobre el ardor sin afirmar lo que no contó |
| "tengo la presión alta, ¿qué debo hacer?" | Mensaje fijo y frases sobre "la molestia en el pecho", que la persona no mencionó | Sí | Responder qué hacer con la presión alta |
| "¿qué puedo comer si tengo la presión alta?" | Mensaje fijo; primero el sodio ("opciones similares", sin antecedente) y al final DASH | Sí | Empezar por la respuesta directa; sin frases sueltas |
| "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | **Instrucciones de una convulsión** ("protege la cabeza", "no sujetes sus movimientos"), 5/5 frases respaldadas, con un registro de sangrado disponible (0,63) | Sí | **No mostrar instrucciones de otra emergencia** |
| "siento el pecho pesado cuando subo escaleras" | Urgencia inmediata por código | No | Nada: la alarma no cambia |

El caso del sangrado es el más grave: la verificación aceptó todas las frases porque están en el registro citado. Es una falla de pertinencia presente hoy en `main`, y por eso la compuerta del paso 1.1 lo exige.

## Puntos por decidir
Son propuestas. Cada una indica qué paso bloquea.

### 1. Avisos de atención que el selector deja por fuera (bloquea el paso 1.2; decide el equipo clínico)
El refuerzo solo cubre los registros **elegidos**. Si el selector dice `no_responde`, o elige otro registro, un aviso como "ve a urgencias" no se muestra, y es el LLM quien lo dejó por fuera, en tensión con el ADR 0004. Hoy ya puede pasar al redactar, pero el literal conserva los avisos del registro principal. Reforzar siempre los avisos de todos los registros tiene el costo contrario: vuelven las remisiones sin relación con la consulta, como el registro de preeclampsia en la acidez (2026-10-24).

**Propuesta:** medir antes de decidir. En `observar`, la traza registra los avisos de los registros ofrecidos que el selector omitió (`omitted_notices`). Con esos casos, el equipo clínico elige entre:
- (a) reforzar solo los registros elegidos, como en el plan;
- (b) reforzar además el aviso del registro de mayor similitud;
- (c) reforzarlo solo si comparte tema con la consulta.

**Evidencia de la línea base:** el refuerzo sobre los registros elegidos tampoco es inocuo. En el caso del ardor, el selector podría elegir, con razón, "el reflujo puede causar ardor torácico", y el refuerzo volvería a agregar "busca atención de urgencias inmediatamente", un aviso que en ese registro depende de un dolor con sudor frío. Por eso el paso 1.1 también registra qué avisos se **agregarían** (`added_notices`), y las opciones anteriores se evalúan con los dos datos.

Las alarmas deterministas no dependen de esto: se evalúan antes y el selector nunca las ve ni las quita.

### 2. El veredicto llega después de la regla (bloquea el paso 1.2)
La regla de la HU-11 decide antes de que exista el veredicto, y `no_responde` obliga a decidir de nuevo.

**Propuesta:** la regla decide primero; si el modo muestra evidencia, corre el selector, y una función pura de `inquiry_policy.py` (`mode_after_selection`) da el modo final. La traza guarda ese modo final, que es el que cuenta para los turnos de indagación, y `InquiryTrace` conserva el modo que eligió la regla.

| Modo de la regla | Veredicto | Condición | Modo final |
|---|---|---|---|
| Responder | `responde` | — | Responder |
| Responder | `parcial` | Sin pedido directo, con síntomas y con turnos disponibles | Responder e indagar (paso 1.3; antes, responder) |
| Responder | `parcial` | En otro caso | Responder |
| Responder | `no_responde` | Sin pedido directo, con síntomas y con turnos disponibles | Indagar |
| Responder | `no_responde` | En otro caso | Abstención o cierre (`no_answer_mode`) |

Un veredicto con `selected` vacío cuenta como `no_responde`. Con `no_responde` se ignoran los ids. Un id fuera del `enum` o un JSON inválido cuentan como fallo del selector.

### 3. Combinaciones con otros modos y alarmas (bloquea el paso 1.2)
**Propuesta:**
- **`INQUIRY_MODE` en `apagado` u `observar` con selección `activo`:** no hay regla que indague, así que `no_responde` muestra la abstención (`no_evidence_text`). Responder e indagar solo existe con los dos en `activo`.
- **Alarma prioritaria nueva:** el mensaje fijo siempre se muestra. Con `responde` o `parcial`, va con la respuesta y nunca se pregunta; con `no_responde`, va solo.
- **Urgencia recordada (B-030):** selector y redactor reciben URGENCIA EN CURSO; `no_responde` deja solo el recordatorio y nunca se pregunta.
- **Pedido directo o pregunta de información:** nunca se pregunta.

### 4. Citas y verificación (bloquea el paso 1.2)
Hay dos caminos: citar la frase (`E2.3`), que obliga a parafrasear una sola frase y falla si el redactor une dos, o citar el registro (`E2`) con su texto reducido.

**Propuesta:** el redactor cita `E2`. Cada registro se le entrega reducido a sus frases seleccionadas, sin la pregunta del registro, y esa versión reducida es contra la que se verifica. Así `compose_grounded_reply` no cambia de regla y una palabra de una frase no seleccionada no da respaldo. La traza sigue mostrando los registros originales.

El literal necesita un camino propio, porque hoy muestra solo el registro principal: las frases seleccionadas y reforzadas de todos los registros, en el orden del selector, sin preguntas.

### 5. Frases que dependen de la anterior (bloquea el paso 1.1)
Una frase suelta puede perder su sentido ("Eso no es normal", "En ese caso, consulta"). El selector ve los ids en orden, pero nada le impide tomar solo la segunda.

**Propuesta:**
- el prompt pide elegir las dos cuando una depende de la otra;
- una regla determinista agrega la frase anterior del mismo registro si la elegida empieza con un marcador de continuación (`eso`, `esto`, `ahí`, `por eso`, `en ese caso`, `entonces`). La lista se ajusta con lo que se observe en `observar`.

La condición dentro de una misma frase ("si tiene fiebre, …") no se ve afectada, porque la frase va completa.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Revisor posterior que evalúa la respuesta redactada | No cambia el flujo actual | Repite el trabajo del redactor y, si rechaza, obliga a otra redacción o al literal. Decisión del usuario: sin revisores que dupliquen |
| Selector que reescribe la evidencia | Podría juntar ideas | Puede inventar texto; con ids no puede |
| Mejorar solo el prompt v4 | Sin llamada nueva | Mezcla dos tareas, y el literal sigue siendo léxico |
| Reforzar siempre todos los avisos | Nunca se pierde una remisión | Vuelven las remisiones ajenas a la consulta (punto 1) |
| Selector como regla léxica | Sin LLM | Es lo que hace `pertinent_sentences`: no entiende sinónimos ni la situación |

## Consecuencias
- ✅ Cada agente hace una tarea, y lo que elige el selector queda auditable frase por frase.
- ✅ El literal mejora: ya no depende de coincidencias de palabras.
- ✅ Se apaga por `.env`, sin revertir código.
- ⚠️ El selector puede descartar una frase útil o un aviso: se mide en `observar` y es la razón del punto 1.
- ⚠️ Un turno con evidencia hace una llamada más al modelo de respuesta. La latencia no es objetivo de este plan, pero se registra en `timings` y `model_usage`.
- ⚠️ Si el contenido no tiene nada aplicable, ningún agente lo resuelve sin inventar. Por eso la etapa 2 del plan (B-032) registra los vacíos para el equipo clínico.
- ⏳ Pendiente: revisión de este ADR y de la HU-13, y los puntos por decidir.
