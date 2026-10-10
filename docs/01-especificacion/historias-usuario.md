# Historias de usuario

*Última actualización: 2026-10-10*

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

Notas técnicas: cada hilo es un JSON (`id`, `domain`, `summary`, `status`) y cada mensaje lleva su `thread_id`. El agente responde en JSON estructurado y decide si el mensaje continúa el hilo o abre uno nuevo. Al agente solo se envía el resumen del hilo actual y sus últimos N mensajes (ADR 0006).

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

### HU-02: Orientación en salud
**Como** gestante o cuidador, **quiero** hacer preguntas en mis propias palabras, **para** recibir información clara y confiable.
Estado: ⏳ Borrador. TODO: criterios.

### HU-03: Alerta por signos de alarma materno‑infantiles
**Como** gestante o cuidador de un menor, **quiero** que el asistente reconozca si lo que describo es peligroso, **para** acudir a tiempo.
Estado: ⏳ Borrador. TODO: criterios (dependen de RN-MI).

### HU-04: Alerta por signos de alarma cardiovasculares
**Como** persona con riesgo cardiovascular, **quiero** saber si mis síntomas requieren atención urgente, **para** actuar a tiempo.
Estado: ⏳ Borrador. TODO: criterios (dependen de RN-CV).

### HU-05: Ruta de atención
**Como** usuario con una alerta, **quiero** saber a dónde acudir en mi municipio, **para** recibir atención oportuna.
Estado: ⏳ Borrador. TODO: criterios (dependen de RN-RUTA).
