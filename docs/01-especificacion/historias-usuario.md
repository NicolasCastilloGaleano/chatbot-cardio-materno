# Historias de usuario

*Última actualización: 2026-10-10 (HU-03/HU-04)*

Formato: *Como [rol], quiero [acción], para [beneficio]*. Los criterios de aceptación van en Gherkin. El estado se sincroniza con el [backlog](../00-gestion/backlog.md) y la [trazabilidad](trazabilidad.md).

> Borradores iniciales derivados de la propuesta. TODO: validar con los aliados.

### HU-00: Conversación libre con el modelo por consola (prueba técnica)
**Como** integrante del equipo de desarrollo, **quiero** escribir mensajes en la consola y recibir la respuesta del modelo de lenguaje local (Ollama), **para** verificar que la integración con el LLM funciona antes de construir el flujo clínico.

> ⚠️ Prototipo técnico **sin reglas de alarma** (riesgo R-07). No se debe usar con usuarios reales.

```gherkin
Escenario: Conversación básica
  Dado que Ollama está activo con el modelo configurado en OLLAMA_MODEL
  Cuando ejecuto el programa y escribo "Hola, tengo dudas sobre la alimentación en el embarazo"
  Entonces la consola muestra la respuesta del modelo en español
  Y puedo seguir escribiendo y el modelo recuerda lo dicho antes en la misma sesión

Escenario: Salir de la consola
  Dado que el chat está abierto
  Cuando escribo "salir"
  Entonces el programa se despide y termina

Escenario: Ollama no disponible o modelo no instalado
  Dado que Ollama no responde o el modelo no está descargado
  Cuando ejecuto el programa
  Entonces veo un mensaje claro en español que explica cómo solucionarlo
  Y el programa termina sin mostrar un traceback

Escenario: Error durante la conversación
  Dado que el chat está abierto
  Cuando una llamada al modelo falla (p. ej., por timeout)
  Entonces veo un mensaje de error claro y el chat sigue abierto
```
Estado: ✅ Aceptada (verificada en el PC de pruebas el 2026-10-10)

### HU-06: Hilos conversacionales con resumen
**Como** persona que consulta al asistente, **quiero** que recuerde de qué estamos hablando en mi consulta actual y que distinga cuando cambio de tema, **para** recibir respuestas coherentes sin que mezcle casos distintos.

Notas técnicas: cada hilo es un JSON (`id`, `domain`, `summary`, `status`) y cada mensaje lleva su `thread_id`. **Desde la HU-02 (ADR 0008)** el resumen lo escribe la llamada de análisis, antes de la respuesta del turno: cada respuesta entra al resumen en el turno siguiente (siempre está completa en los mensajes recientes), salvo la última respuesta de un hilo que se cierra. El agente responde en JSON estructurado y decide si el mensaje continúa el hilo o abre uno nuevo. Al agente solo se envía el resumen del hilo actual y sus últimos N mensajes (ADR 0006).

```gherkin
Escenario: El primer mensaje crea un hilo
  Dado que no hay un hilo activo en la sesión
  Cuando escribo "Estoy embarazada de 5 meses y tengo mucha acidez"
  Entonces se crea un hilo con un identificador único y estado "abierto"
  Y el agente clasifica el dominio como "materno_infantil" y escribe un resumen
  Y mi mensaje y la respuesta quedan guardados con el identificador del hilo

Escenario: Un mensaje relacionado continúa el hilo
  Dado que hay un hilo abierto sobre acidez en el embarazo
  Cuando escribo "¿Qué puedo comer para eso?"
  Entonces el mensaje se agrega al mismo hilo
  Y el resumen del hilo se actualiza

Escenario: Un cambio de tema cierra el hilo y abre uno nuevo
  Dado que hay un hilo abierto sobre acidez en el embarazo
  Cuando escribo "Otra cosa, mi papá tiene la presión alta"
  Entonces el hilo anterior queda en estado "cerrado"
  Y se crea un hilo nuevo con dominio "cardiovascular"

Escenario: El contexto enviado al agente está acotado
  Dado un hilo abierto con más de N mensajes
  Cuando escribo un mensaje nuevo
  Entonces al agente solo se envían el prompt de sistema, el JSON del hilo actual, los últimos N mensajes del hilo y el mensaje nuevo

Escenario: Salir cierra el hilo activo
  Dado que hay un hilo abierto
  Cuando escribo "salir"
  Entonces el hilo queda en estado "cerrado" en su archivo JSON

Escenario: Respuesta inválida o error del modelo
  Dado que el modelo falla o no devuelve el JSON esperado
  Cuando escribo un mensaje
  Entonces veo un mensaje de error claro, no se guarda nada en el hilo y el chat sigue abierto
```
Estado: ✅ Aceptada (verificada en el PC de pruebas el 2026-10-10)

### HU-01: Inicio de conversación y consentimiento
**Como** persona de la comunidad, **quiero** saber qué hace el asistente y aceptar el uso de mis datos, **para** usarlo con confianza.
```gherkin
Escenario: Primer contacto
  Dado que es la primera vez que escribo
  Cuando envío cualquier mensaje
  Entonces recibo un saludo, el aviso de teleorientación y la solicitud de consentimiento
```
Estado: ⏳ Borrador

### HU-02: Orientación en salud con evidencia
**Como** gestante o cuidador, **quiero** hacer preguntas en mis propias palabras, **para** recibir información clara y confiable, respaldada por la base de conocimiento del proyecto.

Notas técnicas (ADR 0008): búsqueda híbrida sobre `knowledge/kb/entries.jsonl` (1.600 registros, validados para el prototipo por el líder del proyecto). Dos llamadas al agente: **análisis sin evidencia** (hilo, resumen, síntomas → filtro 2) y **respuesta con evidencia**. Solo evidencia para afirmaciones de salud.

```gherkin
Escenario: Respuesta respaldada por evidencia
  Dado que la base de conocimiento y su índice están disponibles
  Cuando pregunto "¿por qué es importante controlar la presión si no me duele nada?"
  Entonces se recuperan registros con similitud ≥ al umbral de la política
  Y la respuesta usa solo esa evidencia y cita sus etiquetas en evidence_ids
  Y la respuesta guarda en el hilo la evidencia ofrecida, la citada y los tiempos de cada etapa

Escenario: Sin evidencia suficiente
  Cuando pregunto algo que la base no cubre
  Entonces el asistente dice que no tiene información validada sobre eso y sugiere consultar con el personal de salud
  Y no cita evidencia

Escenario: La evidencia nunca llega al análisis
  Cuando el asistente procesa cualquier mensaje
  Entonces la llamada de análisis (que produce los síntomas del filtro 2) no recibe evidencia
  Y solo la llamada de respuesta la recibe

Escenario: Urgencias sin búsqueda de evidencia
  Dado que el filtro 1 o el filtro 2 detectan una urgencia inmediata
  Entonces no se busca evidencia ni se hace la llamada de respuesta, y se muestra el mensaje fijo

Escenario: Solo se pueden citar las etiquetas ofrecidas
  Cuando el agente cita una etiqueta de evidencia que no se le ofreció
  Entonces el turno falla con un error claro y no se guarda nada

Escenario: RAG no disponible
  Dado que el índice no existe, el modelo de embeddings no coincide o falla
  Cuando el asistente arranca o responde
  Entonces avisa que el RAG no está disponible y se abstiene de dar información de salud
```
Estado: 🔄 En verificación (falta el guion y la sonda en vivo en el PC de pruebas)

### HU-03: Alerta por signos de alarma materno‑infantiles
**Como** gestante o cuidador de un menor, **quiero** que el asistente reconozca si lo que describo es peligroso, **para** acudir a tiempo.
Reglas: `RN-MI-01` a `RN-MI-14` (catálogo PROVISIONAL, ADR 0007). Desde la HU-02 (ADR 0008), los `reported_symptoms` del filtro 2 los produce una **llamada de análisis que nunca recibe evidencia del RAG**, para que la base de conocimiento no contamine ni minimice los síntomas.
```gherkin
Escenario: Urgencia materno-infantil en el mensaje del usuario
  Dado que el catálogo de alarmas está cargado
  Cuando escribo "estoy embarazada y tengo un sangrado"
  Entonces el asistente responde solo con el mensaje fijo de urgencia (acudir a urgencias o llamar al 123)
  Y no se consulta al modelo de lenguaje
  Y se registra en el hilo una alerta con la regla RN-MI-01, severidad "urgencia_inmediata" y origen "usuario"

Escenario: Alarma detectada en los síntomas que reporta el agente
  Dado que mi mensaje no coincide con ninguna regla ("me está saliendo agüita rosada por abajo")
  Y el agente reporta el síntoma "sangrado vaginal en el embarazo"
  Cuando se revisan los síntomas reportados con las mismas reglas
  Entonces se descarta la respuesta del agente y se muestra solo el mensaje fijo de urgencia
  Y la alerta queda registrada con origen "agente"

Escenario: Descripción coloquial de un sangrado (regresión del 2026-10-10)
  Cuando escribo "me está saliendo como agüita rosada por abajo, tengo 7 meses"
  Entonces se activa RN-MI-01 y el asistente responde solo con el mensaje fijo de urgencia

Escenario: El agente usa el nombre del signo del catálogo (regresión 2 del 2026-10-10)
  Cuando escribo "siento que el bebé ya no patea igual que antes, tengo 8 meses"
  Entonces se activa RN-MI-06
  Y si el agente reporta "Disminución o ausencia de movimientos fetales: …", la regla también se activa por su nombre

Escenario: Los síntomas reportados por el agente quedan registrados
  Cuando el agente responde un mensaje
  Entonces su respuesta en el JSON del hilo incluye "reported_symptoms" (lista vacía si no hubo síntomas)
  Y la línea de depuración muestra los síntomas reportados o indica que el agente no fue consultado

Escenario: Los consejos del agente no generan alarmas
  Dado que pregunto "¿qué signos de alarma hay en el embarazo?"
  Cuando el agente menciona el sangrado como signo de alarma en su respuesta o en su resumen
  Y no reporta síntomas de la persona
  Entonces no se registra ninguna alerta
```
Estado: ✅ Verificada técnicamente en el PC de pruebas (2026-10-10). Reglas PROVISIONALES: falta la validación clínica

### HU-04: Alerta por signos de alarma cardiovasculares
**Como** persona con riesgo cardiovascular, **quiero** saber si mis síntomas requieren atención urgente, **para** actuar a tiempo.
Reglas: `RN-CV-01` a `RN-CV-06` (catálogo PROVISIONAL, ADR 0007).
```gherkin
Escenario: Urgencia cardiovascular
  Cuando escribo "tengo un dolor muy fuerte en el pecho"
  Entonces el asistente responde solo con el mensaje fijo de urgencia cardiovascular
  Y se registra una alerta RN-CV-01 "urgencia_inmediata"

Escenario: Consulta prioritaria por presión alta sin síntomas
  Cuando escribo "mi papá tiene la presión alta"
  Entonces el asistente muestra primero el mensaje fijo de consulta prioritaria y luego su orientación
  Y se registra una alerta RN-CV-06 "consulta_prioritaria"

Escenario: La alarma prioritaria se muestra aunque falle el modelo
  Dado que el modelo de lenguaje no responde
  Cuando escribo "tengo la presión alta"
  Entonces veo el mensaje fijo de consulta prioritaria y la alerta queda registrada

Escenario: El agente puede elevar la severidad, nunca reducirla
  Dado que mi mensaje activa una consulta prioritaria
  Cuando el agente reporta un síntoma de urgencia inmediata
  Entonces se muestra el mensaje fijo de urgencia y se registran ambas alertas (usuario y agente)
```
Estado: ✅ Verificada técnicamente en el PC de pruebas (2026-10-10). Reglas PROVISIONALES: falta la validación clínica

### HU-05: Ruta de atención
**Como** usuario con una alerta, **quiero** saber a dónde acudir en mi municipio, **para** recibir atención oportuna.
Estado: ⏳ Borrador. TODO: criterios (dependen de RN-RUTA).

### HU-07: Control de alcance de la conversación
**Como** responsable del servicio, **quiero** que el asistente solo atienda consultas de salud cardiovascular y materno-infantil, **para** que no se use para otros temas, sin descartar consultas reales que mencionen otros temas como contexto.

Criterio (definido por Nicolas Castillo Galeano): se descarta un mensaje **solo si todo el mensaje** es ajeno al servicio. Notas técnicas: ADR 0009.

```gherkin
Escenario: Mensaje completamente ajeno
  Cuando escribo "¿qué opinas del fútbol?"
  Entonces el asistente responde con el mensaje fijo de alcance del servicio
  Y no busca evidencia ni hace la llamada de respuesta
  Y no se registra nada en el hilo

Escenario: Otro tema mencionado solo como contexto
  Cuando escribo "estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas, ¿es normal?"
  Entonces el mensaje se atiende como consulta de salud materna, con evidencia

Escenario: Mensaje mixto
  Cuando escribo "¿quién ganó el partido? ah, y tengo la presión alta"
  Entonces el asistente responde solo la parte de salud y dice con amabilidad que sobre lo demás no puede ayudar

Escenario: Seguimiento dentro de un hilo
  Dado un hilo sobre la fiebre de mi bebé en el que el asistente preguntó desde cuándo
  Cuando escribo "sí, desde ayer"
  Entonces el mensaje se atiende dentro del mismo hilo

Escenario: Mensaje ajeno en medio de una consulta
  Dado un hilo abierto sobre acidez en el embarazo
  Cuando escribo "¿quién ganó el partido?" y luego "¿y qué más puedo comer?"
  Entonces el primer mensaje recibe el mensaje fijo y no se registra
  Y el segundo continúa el mismo hilo

Escenario: Saludo o agradecimiento
  Cuando escribo "hola" o "gracias"
  Entonces el asistente responde con amabilidad y presenta el servicio, sin buscar evidencia
  Y si hay un hilo activo, su dominio no cambia

Escenario: Las alarmas tienen prioridad sobre el alcance
  Cuando un mensaje activa una alarma (filtro 1 o filtro 2), aunque hable de otro tema
  Entonces se responde la alarma y el mensaje nunca se trata como fuera de alcance
```
Estado: 🔄 En verificación (falta `pytest -m live` y el guion en el PC de pruebas)
