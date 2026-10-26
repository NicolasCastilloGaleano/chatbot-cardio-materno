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
