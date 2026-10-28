# ADR 0017: Indagación guiada por la evidencia

- **Estado:** Aceptado (2026-10-27) como especificación. Los umbrales y el texto del cierre son propuestas: los umbrales se calibran en modo `observar` y el texto lo revisa el equipo clínico
- **Fecha:** 2026-10-26
- **Decisores:** equipo del proyecto (Nicolas Castillo Galeano y equipo clínico para los umbrales y el texto de cierre)
- **Modifica:** ADR 0010 (el LLM puede redactar sin evidencia, pero solo preguntas verificadas) y ADR 0008 (una tercera clase de llamada de respuesta)
- **Historia:** HU-11

## Contexto
Hoy cada turno sin alarma busca evidencia y, si hay registros sobre el umbral (0,50), responde con ellos; si no, se abstiene. El asistente no **indaga**: con un mensaje vago ("tengo un ardor raro") responde con el registro más parecido, que a veces es de otro tema, o se abstiene.

La migración a la base v2 intentó resolver la indagación con registros escritos por etapas y una máquina de estados, y empeoró el funcionamiento (ver la [revisión de la base v2](../../00-gestion/anexos/revision-base-rag2.md)).

El equipo decidió permitir que el agente indague con su propio conocimiento, con dos condiciones:
- la indagación tiene que servir para que el RAG encuentre evidencia útil, porque una conversación larga que termina sin respuesta desperdicia tiempo y confianza;
- tiene que detenerse cuando no se está llegando a nada.

## Decisión
1. **Tres modos por turno, decididos por una regla determinista** (`application/inquiry_policy.py`, sin el LLM): **responder**, **indagar** o **cerrar**. Las alarmas se evalúan antes, como hoy (ADR 0007): con cualquier alarma no se indaga.
2. **El RAG busca en todos los turnos**, con la consulta del análisis (`search_query`), que acumula lo dicho en el hilo, y con la búsqueda ampliada a los dos dominios (B-025). Señales que usa la regla:
   - `s1`: el mejor puntaje;
   - `margen`: la diferencia entre el primero y el segundo;
   - `coincidencia`: cuántos de los mejores registros comparten la categoría del primero;
   - `avance`: si `s1` subió al menos `delta` respecto al turno anterior, o si la categoría del primero se mantuvo.
   - **candidatos** (2026-10-27): hoy el buscador descarta lo que no llega a `min_similarity`. `RetrievalResult` agrega `candidates`, los mejores registros con similitud ≥ `piso_indagacion`. Las señales se calculan sobre ellos. Solo guían la indagación: nunca se citan ni se muestran como evidencia.
3. **Regla, en este orden** (los valores son propuestas iniciales, configurables y calibrados en el PC):

   | Condición | Modo |
   |---|---|
   | `s1 ≥ umbral_respuesta` (0,60) y (`margen ≥ margen_min` (0,03) o `coincidencia ≥ 2`) | responder |
   | La persona pide orientación directa (`wants_guidance`) y `s1 ≥ min_similarity` (0,50) | responder |
   | Turno de indagación ≥ `max_turnos` (3), o dos turnos seguidos sin avance | responder si `s1 ≥ min_similarity`; si no, cerrar |
   | `s1 ≥ piso_indagacion` (0,40) | indagar |
   | Primer turno del tema bajo el piso | abstención que pide detalles (HU-02) |
   | Ya se pidió detalle y sigue bajo el piso | cerrar |

4. **Turno de indagación:**
   - una llamada al modelo de respuesta con un prompt nuevo (`inquiry_prompt_v1.md`), que recibe el resumen del hilo, los mensajes recientes y los **candidatos**: categoría, pregunta y respuesta de los 2 o 3 mejores registros, en especial los de enfoque *Indagar*, que dicen qué datos importan;
   - la instrucción es preguntar lo que **diferencia** a los candidatos y lo que la persona aún no dijo, en 1 o 2 preguntas, sin nombrar diagnósticos;
   - la evidencia nunca llega a la llamada de análisis (ADR 0008);
   - **los registros *Indagar* son un insumo opcional** (2026-10-27, consideración del usuario): el agente los usa si encajan con lo que contó la persona y reformula sus preguntas con naturalidad. Si no encajan, o no hay, pregunta con su propio conocimiento. En ambos casos la meta es acercarse a un registro de la base o llegar al cierre honesto, nunca explorar por explorar. Las preguntas se verifican igual (punto 5).
5. **Verificación del turno de indagación** (determinista, en `domain/grounding.py`): solo se aceptan preguntas cortas sin números y frases de cortesía. Es la regla actual de `is_allowed_without_citation`, con un máximo propio de frases por turno. Si no queda ninguna pregunta válida, se usa una pregunta fija. Así se mantiene la regla de oro: **ninguna afirmación de salud sin respaldo verificable**.
6. **Pedido de orientación directa:** el análisis agrega un campo booleano `wants_guidance` ("¿qué hago?"). Requiere el **prompt de análisis v7**, que se registra en `docs/05-ia/prompts/README.md`. El análisis solo traduce el lenguaje: la regla decide. El v7 agrega además `about_health` (ADR 0009, actualización 2026-10-27), para que un mensaje ajeno en un hilo con síntomas no quede en alcance ni termine en una indagación.
7. **Estado sin almacenamiento nuevo:** el modo, el turno de indagación y las señales viajan en la **traza** de cada respuesta. El turno siguiente las lee de los mensajes recientes del hilo. No cambia el esquema SQLite. Un hilo nuevo reinicia el conteo. `context_messages` (6) debe cubrir al menos los últimos `max_turnos` turnos.
8. **Cierre honesto:** un texto fijo, sin llamar al LLM: no hay información validada sobre eso, recomienda consultar con el personal de salud y ofrece hablar de otro tema. El texto lo aprueba el equipo. Propuesta (2026-10-27): "Con lo que me cuentas no encuentro información validada en la base del proyecto para orientarte sobre esto. Te recomiendo consultarlo con el personal de salud de tu EPS o centro de salud. Si tienes otra duda sobre el corazón, la presión arterial, el embarazo o tu bebé, con gusto te ayudo."
9. **Activación gradual** con `INQUIRY_MODE` en `.env`:
   - `apagado`: comportamiento actual, sin calcular nada;
   - `observar` (por defecto en la primera entrega): la regla calcula el modo y lo registra en la traza, pero el turno se resuelve como hoy, para calibrar los umbrales con conversaciones reales;
   - `activo`: la regla decide el turno.
10. **Auditoría y métricas:** la interfaz web y la depuración de la consola muestran el modo, el turno de indagación y las señales. Las métricas de utilidad de la HU-11 se miden en el PC: porcentaje de indagaciones que terminan con evidencia, turnos promedio hasta responder, indagaciones perdidas y afirmaciones de salud en los turnos de indagación.

## Puntos decididos (2026-10-27, Nicolas Castillo Galeano)
- Los umbrales del punto 3 (0,40 / 0,60 / margen 0,03 / máximo 3 turnos) se mantienen como propuesta inicial y se calibran con las trazas del modo `observar`, antes de pasar a `activo`.
- Las metas de utilidad de la HU-11 se mantienen (≥ 70 % / ≤ 2 turnos / ≤ 20 % perdidas).
- El texto del cierre del punto 8 es una propuesta que revisa el equipo clínico.
- Los registros *Indagar* son un insumo opcional (punto 4).
- Orden: primero B-028 (pertinencia de la respuesta y literal por frases, ADR 0010), porque mejora lo que ya existe y la indagación termina en esas respuestas. Después la HU-11 en `observar` (candidatos, v7, regla, traza) y al final en `activo` (prompt de indagación, verificación y cierre).
- La ampliación de una respuesta con conocimiento propio del agente (HU-12, B-029) **no** es parte de este ADR: cambia la regla de oro del ADR 0010 y se tratará aparte, con su propio ADR y el aval clínico.

## Implementación de la fase 2 (2026-10-27, modo observar)
- Valores que el ADR no fijaba: `delta` de avance 0,02 y "dos turnos seguidos sin avance" como `max_stalled` = 2, ambos configurables (`INQUIRY_PROGRESS_DELTA`, `INQUIRY_MAX_STALLED`). La coincidencia cuenta los candidatos con la categoría del primero, **incluido el primero** (`coincidencia ≥ 2` = al menos otro candidato de la misma categoría).
- El modo "abstención que pide detalles" de la tabla queda como `abstenerse` en `TurnMode`.
- En modo observar, el estado del turno siguiente sale de la decisión **simulada** (lo que la regla habría hecho), aunque la persona recibió la respuesta de siempre. Así la calibración refleja la secuencia de la regla, con esa limitación.
- `activo` todavía no está implementado: si se configura, se observa y se avisa al arrancar.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Base v2 por etapas y máquina de estados (migración) | La indagación está escrita y validable | Registros atados a un caso de ejemplo, peor recuperación y mucha complejidad. Se revirtió el 2026-10-26 |
| Que el LLM decida cuándo dejar de indagar | Simple y flexible | Contradice ADR 0004. No es auditable ni reproducible, y puede indagar sin fin |
| Indagar siempre un número fijo de turnos | Predecible | Indaga aunque la evidencia ya sea clara y no se detiene cuando no hay nada que encontrar |
| Usar solo los registros *Indagar* como texto literal | Todo tiene respaldo | Son instrucciones genéricas ("Describe…, Cuenta…"), no se adaptan a lo dicho y suenan a formulario |
| **Indagación del agente guiada por las señales del RAG (elegida)** | Pregunta lo que acerca a la evidencia, se detiene si no hay avance y es auditable | Más llamadas al LLM en los turnos de indagación y umbrales que hay que calibrar |

## Consecuencias
- ✅ Antes de orientar, el asistente caracteriza la situación, y la evidencia final corresponde mejor a lo que le pasa a la persona.
- ✅ La indagación tiene un final garantizado: responde o cierra en un máximo de `max_turnos` turnos.
- ✅ Sigue sin haber afirmaciones de salud sin respaldo. Las preguntas se verifican igual que hoy las frases sin cita.
- ⚠️ Cada turno de indagación cuesta análisis, RAG y una llamada al LLM, como un turno de respuesta (unos 45–60 s en el PC). Con 2 o 3 preguntas, la conversación hasta la respuesta es más larga. El máximo de turnos lo limita.
- ⚠️ Una pregunta puede insinuar algo ("¿sabías que…?"). Se mitiga con el límite de longitud, sin números y con la traza; queda a vigilar.
- ⚠️ Los umbrales (0,40 / 0,60 / margen / delta) son una propuesta: se calibran en modo `observar` antes de activar.
- ⚠️ Cambia el prompt de análisis (v7, campo `wants_guidance`). Hay que repetir `pytest -m live` de alcance y filtro 2.
- Pendiente: calibración de los umbrales en modo `observar` y revisión clínica del texto del cierre.
