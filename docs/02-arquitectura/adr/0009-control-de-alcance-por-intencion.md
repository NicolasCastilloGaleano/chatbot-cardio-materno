# ADR 0009: Control de alcance por intención en la llamada de análisis

- **Estado:** Aceptado
- **Fecha:** 2026-10-10
- **Decisores:** Nicolas Castillo Galeano (criterio de alcance definido por él)
- **Relacionado:** ADR 0007 (alarmas), ADR 0008 (dos llamadas y RAG)

## Contexto
En la prueba en el PC de pruebas, "¿qué opinas del fútbol?" recibió una charla sobre fútbol. No había control de alcance y el prompt de respuesta permitía conversar sin evidencia.

El criterio del usuario: se descarta un mensaje **solo si todo el mensaje** es ajeno a la salud cardiovascular o materno-infantil. Las menciones a otros temas que solo dan **contexto** no lo sacan del alcance, como en "estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas, ¿es normal?". Tampoco los mensajes que solo tienen sentido dentro del hilo, ni los que aún no tienen dominio claro pero pueden pertenecer a uno de los dos.

## Decisión
1. **La llamada de análisis decide el alcance por intención**: `scope` = `en_alcance` | `conversacional` | `fuera_de_alcance`, más un `scope_reason` corto. El prompt (`analysis_prompt_v2.md`) indica evaluar el **propósito del mensaje completo** junto con el hilo, trae una tabla de ejemplos y dice: **ante la duda, `en_alcance`**.
2. **No se usan palabras clave** para descartar, porque descartarían consultas legítimas con contexto ajeno.
3. **Reglas deterministas de seguridad** (`application/scope.py`):
   - si hay `reported_symptoms` **y** el dominio no es `ninguno`, el mensaje es `en_alcance` aunque el modelo diga otra cosa;
   - **las alarmas tienen prioridad**: el filtro 1 corre antes y el filtro 2 se evalúa antes del alcance. Con cualquier alarma, el mensaje nunca se descarta.
4. **Fuera de alcance:** mensaje fijo (plantilla), **sin RAG ni llamada de respuesta**. **No se registra** y no abre, cierra ni modifica el hilo, así que un mensaje ajeno en medio de una consulta no corta el caso.
5. **Conversacional** (saludos, gracias): llamada de respuesta **sin RAG**, solo para saludar y presentar el servicio.
6. **Defensa en profundidad** (`reply_prompt_v2.md`): nunca hablar de temas ajenos; en mensajes mixtos, responder solo la parte de salud.
7. Al continuar un hilo, un análisis con dominio `ninguno` (p. ej., "gracias") **no borra** el dominio del caso.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Filtro por palabras clave | Determinista | Descarta consultas con contexto ajeno ("…viendo el partido y me palpita el corazón") |
| Clasificador antes del filtro de alarmas | Ahorra una etapa | Podría descartar urgencias; contradice el ADR 0007 |
| Registrar los mensajes fuera de alcance en el hilo | Métrica directa | Mezcla temas ajenos en el caso y puede alterar su resumen |
| Solo instrucción en el prompt de respuesta | Simple | El modelo ya ignoró instrucciones parecidas (charla de fútbol) |

## Consecuencias
- ✅ El asistente se mantiene en su propósito sin descartar consultas reales. Además, los mensajes fuera de alcance y los saludos son más rápidos, porque no buscan evidencia y, en el primer caso, tampoco hacen la llamada de respuesta.
- ⚠️ La clasificación depende del LLM (riesgo R-11), mitigada con "ante la duda, en alcance", la salvaguarda de síntomas, las alarmas primero y el `scope_reason` para auditar.
- ⚠️ Los mensajes fuera de alcance no quedan registrados. Si se necesitan métricas de uso indebido, se agregará un contador anónimo en el futuro.

## Actualización 2026-10-17: los síntomas de origen incierto no se descartan
- **Motivo:** "tengo un dolor muy fuerte en el brazo por que me asustó una gallina" se descartaba como fuera de alcance. Un dolor de brazo (sobre todo el izquierdo) puede ser cardíaco aunque la persona lo atribuya a otra causa.
- **Decisión** (Nicolas Castillo Galeano):
  - el prompt de análisis v6 marca "en_alcance" todo mensaje que reporte un síntoma o malestar cuya relación con nuestros dominios no se pueda descartar;
  - "fuera_de_alcance" queda **solo** para mensajes ajenos **sin síntomas** (fútbol, tareas, política);
  - **regla determinista** (`application/scope.py`): basta con que haya `reported_symptoms` para quedar en alcance, aunque el dominio sea "ninguno". Antes, además, se exigía un dominio distinto de "ninguno".
- **Consecuencia:** algunos síntomas que quizás no son de nuestros dominios, como un dolor de muela, ahora pasan a la búsqueda de evidencia. Si no hay evidencia suficiente, reciben la abstención fija (ADR 0010), no un descarte. Que el asistente **pregunte** para aclarar el origen del síntoma, en lugar de abstenerse, es el siguiente paso previsto.

## Actualización 2026-10-26: una respuesta a una pregunta del asistente no se descarta
- **Motivo:** el prompt v6 ya pide tratar como "en_alcance" los mensajes que responden a una pregunta del asistente, pero no había respaldo determinista. Una respuesta corta ("sí, desde ayer", "no sé") podía recibir el mensaje fijo de alcance en medio de una consulta.
- **Decisión:** `effective_scope(analysis, recent)` devuelve "en_alcance" cuando se cumplen las tres condiciones: el análisis dijo "fuera_de_alcance", `thread_action` es "continuar" y el último mensaje del asistente en el hilo contiene "?". Cuenta cualquier pregunta del mensaje, no solo la final.
- **Límites:** un mensaje que el análisis marca como tema nuevo ("¿quién ganó el partido?") sigue recibiendo el mensaje fijo. Los mensajes fuera de alcance siguen sin registrarse, así que el mensaje fijo nunca cuenta como pregunta pendiente.
- **Mensaje fijo de alcance:** desde la misma fecha termina con una pregunta abierta ("¿Tienes alguna duda o molestia sobre estos temas que quieras contarme?") para invitar a seguir, en lugar de cerrar la conversación. Sigue sin registrarse.

## Actualización 2026-10-27: los síntomas acumulados del hilo no dejan en alcance un mensaje ajeno (aprobada, prompt de análisis v7)
**Contexto.** El prompt de análisis v6 repite en `reported_symptoms` lo dicho antes en el hilo, para que el filtro 2 combine el contexto con el signo nuevo. Desde el 2026-10-17, `effective_scope` deja en alcance todo mensaje con síntomas reportados. Juntas, las dos reglas hacen que **cualquier** mensaje en un hilo con síntomas quede en alcance. En el guion de B-027 (2026-10-27), "¿quién ganó el partido?" en el hilo de la fiebre del bebé terminó en una abstención guardada en el hilo, y el resumen del hilo mencionó el partido. Eso contradice el escenario "Mensaje ajeno en medio de una consulta" de la HU-07. Con la HU-11 en modo `activo`, ese mensaje recibiría además una pregunta de indagación.

**Decisión.**
1. El prompt de análisis v7 agrega el booleano `about_health`: si el mensaje **nuevo**, por sí mismo, trata de salud o continúa la conversación de salud del hilo (responde, pregunta o comenta sobre ella).
2. En `effective_scope`, si `about_health` es falso y el análisis no dejó el mensaje en alcance, se respeta su decisión (`fuera_de_alcance` o `conversacional`): ni los síntomas que repite del hilo ni la regla de la pregunta pendiente lo dejan en alcance. Si `about_health` es verdadero, se aplican las reglas de antes: signos o síntomas, respuesta a una pregunta pendiente y, por último, el alcance del análisis.
3. Un mensaje queda fuera de alcance por esta regla solo si **las dos** salidas del análisis lo dicen (`scope` = `fuera_de_alcance` y `about_health` = falso). No cambian ni la prioridad de las alarmas (una alarma nueva siempre deja el mensaje en alcance) ni el recordatorio de una alarma ya avisada, que va antes del mensaje fijo (ADR 0018).
4. **Ajuste al implementar (2026-10-27):** la regla también aplica a la pregunta pendiente. En el guion de B-027, el último mensaje del asistente terminaba en una pregunta y el análisis marcó el partido como "continuar", así que sin este ajuste el partido seguía en alcance por la pregunta pendiente. Una respuesta corta ("sí, desde ayer") queda en alcance porque el prompt v7 la marca con `about_health` verdadero; si falta el campo (prompts anteriores), vale verdadero y nada cambia. De paso, un saludo en un hilo con síntomas vuelve a ser conversacional.

**Consecuencias.**
- ✅ Se cumple el escenario de la HU-07, y la HU-11 no indaga sobre mensajes ajenos.
- ⚠️ Si el análisis marca por error las dos salidas en un mensaje con un síntoma real o en una respuesta a una pregunta del asistente, el mensaje se descarta. Las alarmas del filtro 1 siguen activas. Se vigila repitiendo `pytest -m live` de alcance (incluido el caso del brazo y la gallina, más dos casos nuevos: el partido en un hilo con fiebre y el pedido directo de orientación), obligatorio por el cambio de prompt.

## Actualización 2026-10-28: análisis contradictorio (aprobada por Nicolas Castillo Galeano)
**Contexto.** En la corrida en vivo del 2026-10-28, "¿quién ganó el partido?" en un hilo con fiebre salió con `about_health` falso pero `scope` "en_alcance" (por el tema del hilo). Como la regla del punto 2 solo respetaba el "no es de salud" si el análisis no lo dejaba en alcance, los síntomas del hilo lo volvieron a meter. Antes había pasado lo mismo con un "gracias".

**Decisión.**
1. El prompt v7 exige coherencia: con `about_health` falso, `scope` es "conversacional" (saludos, agradecimientos, despedidas) o "fuera_de_alcance" (temas ajenos), nunca "en_alcance".
2. Respaldo determinista: si el análisis se contradice (`about_health` falso y "en_alcance"), el mensaje se trata como **conversacional**. Recibe una respuesta amable sin RAG ni indagación, queda en el hilo sin cambiar su dominio ni su resumen (HU-07) y el prompt de respuesta no habla del tema ajeno. Se eligió conversacional y no fuera de alcance porque es la salida más segura cuando las señales chocan: un "gracias" no recibe el mensaje de "solo atiendo temas de salud".
3. Sin cambios: las alarmas nuevas siguen teniendo prioridad y el recordatorio de una alarma ya avisada va antes de la respuesta (ADR 0018).

