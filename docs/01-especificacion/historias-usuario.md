# Historias de usuario

*Última actualización: 2026-10-18 (HU-10 propuesta)*

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

Notas técnicas (ADR 0008 y 0010): búsqueda híbrida sobre `knowledge/kb/entries.jsonl` (1.600 registros, validados para el prototipo por el líder del proyecto). Dos llamadas al agente: **análisis sin evidencia** (hilo, resumen, síntomas → filtro 2) y **respuesta con evidencia**. Solo evidencia para afirmaciones de salud.

```gherkin
Escenario: Respuesta respaldada por evidencia
  Dado que la base de conocimiento y su índice están disponibles
  Cuando pregunto "¿por qué es importante controlar la presión si no me duele nada?"
  Entonces se recuperan registros con similitud ≥ al umbral de la política
  Y cada frase de salud de la respuesta cita el registro que la respalda
  Y la respuesta guarda en el hilo la evidencia ofrecida, la citada, la verificación del respaldo y los tiempos de cada etapa

Escenario: Sin evidencia suficiente (abstención determinista, ADR 0010)
  Cuando pregunto algo que la base no cubre ("tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?")
  Entonces se muestra el mensaje fijo de abstención (no tengo información validada; consultar con el personal de salud)
  Y no se llama al modelo de lenguaje para redactar
  Y si hay una alarma prioritaria, se muestra solo su mensaje fijo

Escenario: Cada frase de salud está respaldada por el registro que cita (regresión del 2026-10-11)
  Dado que la evidencia ofrecida es un registro que no habla de alimentación
  Cuando el agente redacta "Come yogur, avena, almendras y nueces" citando ese registro
  Entonces la verificación determinista rechaza la frase
  Y se muestra el texto literal del registro en lugar de la redacción del agente
  Y la traza registra la frase descartada y el uso del texto literal

Escenario: Los avisos no se suavizan
  Dado que el registro dice "necesita atención obstétrica inmediata"
  Cuando el agente lo redacta como "es importante que hables con tu médico"
  Entonces la frase no está respaldada y se muestra el texto literal del registro

Escenario: El texto literal sale del registro más parecido (2026-10-24)
  Dado que la evidencia ofrecida incluye un registro de acidez (similitud 0,60) y uno de preeclampsia (0,55)
  Cuando el agente cita el de preeclampsia con frases que no están en él
  Entonces se muestra el texto literal del registro de acidez, que es el más parecido a la consulta
  Y ante un empate de similitud se usa el registro que citó el agente

Escenario: Frases sin cita
  Cuando el agente agrega una pregunta corta de aclaración o una frase de cortesía sin cita
  Entonces se conservan (máximo 2)
  Y una frase sin cita con información de salud ("Toma infusiones de manzanilla") se descarta

Escenario: La evidencia nunca llega al análisis
  Cuando el asistente procesa cualquier mensaje
  Entonces la llamada de análisis (que produce los síntomas del filtro 2) no recibe evidencia
  Y solo la llamada de respuesta la recibe

Escenario: La búsqueda usa la consulta de salud, sin el contexto ajeno (B-021)
  Cuando escribo "¿quién ganó el partido? ah, y tengo la presión alta"
  Entonces el análisis reformula la consulta de búsqueda solo sobre la presión alta ("search_query")
  Y la evidencia se busca con esa consulta, que queda registrada en la traza

Escenario: Urgencias sin búsqueda de evidencia
  Dado que el filtro 1 o el filtro 2 detectan una urgencia inmediata
  Entonces no se busca evidencia ni se hace la llamada de respuesta, y se muestra el mensaje fijo

Escenario: Solo se pueden citar las etiquetas ofrecidas
  Cuando el agente cita una etiqueta de evidencia que no se le ofreció
  Entonces el turno falla con un error claro y no se guarda nada

Escenario: RAG no disponible
  Dado que el índice no existe, el modelo de embeddings no coincide o falla
  Cuando el asistente arranca o responde
  Entonces avisa al arrancar que el RAG no está disponible
  Y cada consulta de salud recibe el mensaje fijo de abstención, sin llamar al modelo de lenguaje
```
Estado: ✅ Aceptada (verificada en el PC de pruebas el 2026-10-12: `pytest -m live` 24/24, guion con respuestas verificadas, abstenciones y RAG no disponible). La base de conocimiento tiene vacíos (p. ej., alimentación con acidez, diabetes gestacional), que reciben abstención; ampliarla es decisión clínica (B-019)

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

Escenario: Cada síntoma reportado se revisa por separado (regresión del 2026-10-11)
  Dado que el agente reporta "acidez en el embarazo" y "fiebre en el bebé"
  Cuando se revisan los síntomas reportados
  Entonces no se activa RN-MI-07 (fiebre en el embarazo), porque el contexto de un síntoma no se combina con el signo de otro

Escenario: El agente marca el código del signo (ADR 0012, provisional)
  Dado que mi mensaje no coincide con ninguna regla ("el niño no retiene ni el suero")
  Cuando el análisis marca el código VOMITA_TODO en "reported_signs"
  Entonces se activa RN-MI-10 por cruce exacto y se muestra el mensaje fijo de urgencia
  Y la alerta queda registrada con origen "agente_codigo"
  Y un código que no está en el catálogo es un error del modelo y no se guarda nada

Escenario: El análisis no agrega datos que la persona no dijo (regresión del 2026-10-11)
  Dado un hilo sobre "tengo acidez en el embarazo" (sin semanas)
  Cuando escribo "¿y qué más puedo comer?"
  Entonces los síntomas reportados no incluyen semanas ni otros datos que no escribí
  Y si aparecen, la traza los marca en "unstated_symptoms" y la consola muestra "[⚠️ datos que la persona no escribió: …]"

Escenario: La urgencia queda en un hilo de su dominio (regresión del 2026-10-11)
  Dado un hilo materno-infantil activo
  Cuando escribo un signo de alarma cardiovascular ("se me torció la boca y no puedo mover el brazo")
  Entonces se cierra ese hilo y la alerta queda en un hilo nuevo cardiovascular
  Y si la alarma es del mismo dominio del hilo activo, queda en ese hilo
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
  Entonces el asistente responde con el mensaje fijo de alcance del servicio, que termina con una pregunta abierta para seguir conversando (MIG-02)
  Y no busca evidencia ni hace la llamada de respuesta
  Y si no hay un hilo activo, no se registra ni se abre un hilo

Escenario: Síntoma de origen incierto (prompt de análisis v6, 2026-10-17)
  Cuando escribo "tengo un dolor muy fuerte en el brazo por que me asustó una gallina"
  Entonces el mensaje no se descarta: se atiende como consulta de salud
  Y aunque el análisis no sepa a qué dominio pertenece, reportar un síntoma basta para quedar en alcance
  Y un mensaje sin síntomas y ajeno al servicio ("¿qué opinas del fútbol?") sigue recibiendo el mensaje fijo de alcance

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

Escenario: La respuesta a una pregunta del asistente nunca se descarta (MIG-01)
  Dado un hilo cuyo último mensaje del asistente contiene una pregunta (al final o en medio del texto)
  Cuando respondo "no sé" o "desde ayer" y el análisis lo marca fuera de alcance pero como continuación del hilo
  Entonces la regla determinista lo atiende como consulta en alcance, con búsqueda de evidencia
  Y si el análisis lo marca como tema nuevo ("¿quién ganó el partido?"), se respeta su decisión

Escenario: Mensaje ajeno en medio de una consulta
  Dado un hilo abierto sobre acidez en el embarazo
  Cuando escribo "¿quién ganó el partido?" y luego "¿y qué más puedo comer?"
  Entonces el primer mensaje recibe el mensaje fijo y queda registrado en ese hilo, una sola vez, sin cambiar su dominio ni su resumen (MIG-02)
  Y el segundo continúa el mismo hilo

Escenario: Saludo o agradecimiento
  Cuando escribo "hola" o "gracias"
  Entonces el asistente responde con amabilidad y presenta el servicio, sin buscar evidencia
  Y un mensaje conversacional nunca abre un hilo (regresión del 2026-10-11)
  Y si hay un hilo activo, el mensaje queda en ese hilo sin cambiar su dominio ni su resumen
  Y si no hay hilo activo, no se registra

Escenario: Las alarmas tienen prioridad sobre el alcance
  Cuando un mensaje activa una alarma (filtro 1 o filtro 2), aunque hable de otro tema
  Entonces se responde la alarma y el mensaje nunca se trata como fuera de alcance
```
Estado: ✅ Aceptada (verificada en el PC de pruebas el 2026-10-11 y el 2026-10-12: `pytest -m live` de alcance y guion, incluidos el mensaje mixto, los saludos sin hilo y la alarma con otro tema)

### HU-08: Interfaz local de conversación y auditoría
**Como** integrante del equipo de desarrollo, **quiero** conversar con el asistente desde una interfaz web local y consultar la traza asociada a cada respuesta, **para** sustentar y depurar el flujo sin depender temporalmente de Telegram o WhatsApp.

```gherkin
Escenario: Conversar y revisar una respuesta
  Dado que la interfaz local está iniciada
  Cuando envío una consulta de salud y selecciono la respuesta del asistente
  Entonces veo el resumen, dominio y estado del hilo, síntomas, signos, búsqueda, evidencia completa, citas, verificación y tiempos disponibles

Escenario: Mensaje en procesamiento
  Dado que envié un mensaje mientras el agente prepara la respuesta
  Entonces la interfaz muestra que está procesando el mensaje y pide esperar

Escenario: Enviar desde el teclado
  Cuando escribo un mensaje y presiono Enter
  Entonces el mensaje se envía
  Y Shift+Enter inserta una nueva línea sin enviarlo

Escenario: Chat extenso con auditoría a la vista
  Dado que el chat tiene más mensajes de los que caben en su panel
  Cuando continúo la conversación
  Entonces puedo desplazar el historial dentro del panel del chat
  Y los paneles laterales de trazabilidad e hilos permanecen visibles

Escenario: Consultar un hilo guardado
  Dado que hay hilos persistidos
  Cuando selecciono un hilo del historial
  Entonces puedo leer sus mensajes y abrir la traza de sus respuestas
  Y el historial permanece en modo de solo lectura

Escenario: Iniciar una nueva sesión
  Dado que hay una sesión conversacional activa
  Cuando selecciono "Nueva sesión"
  Entonces el hilo activo se cierra y el siguiente mensaje inicia una sesión nueva

Escenario: Mensaje fuera de alcance
  Cuando envío un mensaje completamente ajeno al servicio
  Entonces veo la respuesta fija durante la sesión actual
  Y el mensaje no se agrega al hilo persistido

Escenario: Error del modelo
  Dado que el modelo no responde
  Cuando envío un mensaje
  Entonces veo un error claro y no una traza inventada
```
Estado: ✅ Implementada y verificada automáticamente; falta el recorrido visual en el PC de pruebas. Solo para demostración y depuración local. **La HU-10 la reemplaza en parte:** "Hilos guardados" y "Nueva sesión" pasan a ser una lista de chats por persona y un chat nuevo.

### HU-09: Atención por WhatsApp con historial por persona
**Como** persona de la comunidad, **quiero** consultar al asistente desde mi WhatsApp en un solo chat continuo, **para** recibir orientación sin instalar nada y sin que mis consultas se mezclen con las de otras personas.

Notas técnicas (ADR 0014 y 0015): WhatsApp Cloud API con webhook en FastAPI, cola con un solo trabajador y persistencia SQLite con usuarios, identidades de canal, hilos, mensajes, alertas y eventos. **El agente no cambia:** recibe el mismo contexto que en la consola (prompt de análisis, JSON del hilo activo, últimos N mensajes del hilo, evidencia solo en la respuesta). El aislamiento se logra con un repositorio de hilos acotado a cada usuario. En esta fase solo se atiende a los números de prueba del equipo; el consentimiento (HU-01) queda para la fase siguiente.

```gherkin
Escenario: Verificación del webhook
  Dado que el servidor de WhatsApp está iniciado con WHATSAPP_VERIFY_TOKEN
  Cuando Meta solicita la verificación con hub.mode "subscribe", el token correcto y un challenge
  Entonces el servidor responde el challenge
  Y con un token incorrecto responde 403

Escenario: Solo se aceptan notificaciones firmadas por Meta
  Cuando llega una notificación cuya firma X-Hub-Signature-256 no coincide con WHATSAPP_APP_SECRET
  Entonces se rechaza con 401 y no se procesa

Escenario: Primer mensaje de una persona
  Dado que un número nunca ha escrito
  Cuando envía "tengo 30 semanas y mucha acidez"
  Entonces se crea un usuario ligado al hash del número (nunca el número en claro)
  Y el mensaje se procesa con el mismo flujo de la consola (análisis, filtros, RAG, verificación)
  Y la respuesta llega a ese mismo chat

Escenario: Dos personas no comparten contexto
  Dado que la persona A tiene un hilo abierto sobre acidez en el embarazo
  Y la persona B tiene un hilo abierto sobre presión alta
  Cuando las dos escriben de forma intercalada
  Entonces el contexto enviado al agente en cada turno solo contiene el hilo y los mensajes de quien escribió
  Y cada respuesta llega solo al chat de quien escribió

Escenario: El chat continuo retoma el hilo abierto
  Dado que la persona tiene un hilo abierto con actividad reciente
  Cuando escribe "¿y qué más puedo comer?"
  Entonces el mensaje continúa ese hilo, como en la consola

Escenario: Un hilo inactivo se cierra
  Dado que el hilo abierto de la persona lleva más de THREAD_IDLE_TIMEOUT_HOURS sin actividad
  Cuando escribe un mensaje nuevo
  Entonces ese hilo queda "cerrado" antes de procesar el mensaje
  Y el agente recibe el mensaje sin hilo activo, igual que al iniciar una sesión de consola

Escenario: Un mensaje repetido por Meta no se responde dos veces
  Dado que un mensaje ya fue recibido
  Cuando Meta vuelve a enviar la misma notificación (mismo identificador)
  Entonces no se procesa de nuevo ni se envía otra respuesta

Escenario: Espera mientras se genera la respuesta
  Cuando envío un mensaje
  Entonces se marca como leído y aparece "escribiendo…"
  Y si la respuesta tarda más de WHATSAPP_WAIT_NOTICE_SECONDS, recibo un aviso corto de que se está revisando
  Y si la respuesta llega antes, no recibo el aviso

Escenario: Urgencia por WhatsApp
  Cuando escribo "estoy embarazada y tengo un sangrado"
  Entonces recibo solo el mensaje fijo de urgencia, sin consultar al modelo de lenguaje
  Y la alerta queda registrada en un hilo de mi usuario

Escenario: Mensaje que no es texto
  Cuando envío una nota de voz, una imagen o un sticker
  Entonces recibo un aviso de que por ahora solo se leen mensajes de texto
  Y no se consulta al agente

Escenario: Respuesta larga
  Dado que la respuesta supera el límite de 4096 caracteres de WhatsApp
  Entonces se envía en varios mensajes, sin cortar palabras

Escenario: Error del modelo
  Dado que el modelo no responde y no hay alarma
  Cuando envío un mensaje
  Entonces recibo un mensaje de error claro, no se guarda nada en el hilo y el evento queda como "fallido"

Escenario: Los canales actuales no cambian
  Cuando uso la consola o la interfaz web local
  Entonces funcionan igual que antes, con su repositorio JSON
```
Estado: ✅ Aceptada (verificada en el PC de pruebas el 2026-10-18 con el número de prueba de Meta, ngrok y dos teléfonos: personas separadas, urgencia sin LLM, aviso de "solo texto" con imagen, aviso de espera, reenvío sin duplicar, cierre por inactividad, error del modelo y base sin números). Solo con números de prueba del equipo: falta el consentimiento (HU-01) para personas reales

### HU-10: Auditoría multicanal con chat continuo
**Como** integrante del equipo, **quiero** revisar en la interfaz local los chats de todos los canales (WhatsApp, Telegram, consola y web) como un chat continuo por persona, y seguir conversando en los de consola y web, **para** auditar en qué se basó cada respuesta sin importar por dónde llegó.

Notas técnicas (ADR 0016): la consola y la web pasan a la base SQLite por usuario (ADR 0015). Cada arranque de la consola y cada "Nueva sesión" de la web crean un usuario con su chat. WhatsApp, Telegram y el histórico importado son de solo lectura. **El agente no cambia:** cada turno usa el repositorio acotado al usuario y su hilo abierto.

```gherkin
Escenario: Lista de chats de todos los canales
  Dado que hay chats de WhatsApp, consola y web guardados
  Cuando abro la interfaz
  Entonces veo un chat por persona, del más reciente al más antiguo, con su canal, su última actividad y si es de solo lectura
  Y puedo filtrar por canal (Todos, Consola, Web, WhatsApp, Telegram, Histórico)

Escenario: El chat se carga por partes
  Dado un chat con más de WEB_PAGE_SIZE mensajes
  Cuando lo abro
  Entonces veo solo los WEB_PAGE_SIZE mensajes más recientes
  Y al subir hasta el principio se cargan los anteriores sin perder mi posición, hasta que no queden más

Escenario: Los hilos se distinguen dentro del chat
  Dado un chat con varios hilos
  Cuando lo reviso
  Entonces los mensajes de un mismo hilo comparten color
  Y donde cambia el hilo aparece un separador con su dominio, su estado y su resumen

Escenario: Auditar una respuesta
  Cuando selecciono una respuesta del asistente en cualquier chat
  Entonces queda resaltada y veo su traza: síntomas, signos, búsqueda, evidencia completa, citas, verificación, tiempos y las alertas del turno

Escenario: WhatsApp, Telegram y el histórico son solo de auditoría
  Cuando abro un chat de WhatsApp, de Telegram o el histórico
  Entonces el campo de texto está desactivado y se explica por qué
  Y si se intenta enviar un mensaje a ese chat a través del servidor, se rechaza

Escenario: Nueva sesión en la web
  Cuando selecciono "Nueva sesión"
  Entonces se crea un chat web nuevo, vacío, en el que puedo escribir
  Y ese chat puede tener varios hilos, como el de una persona en WhatsApp

Escenario: La consola crea su propio chat
  Cuando inicio la consola
  Entonces se crea un chat de consola y se muestra su identificador corto
  Y mientras la consola está abierta, en la interfaz ese chat aparece "en uso en la consola" y no se puede escribir en él

Escenario: Continuar en la web un chat de consola
  Dado que cerré la consola con "salir"
  Cuando abro su chat en la interfaz
  Entonces puedo seguir escribiendo en él
  Y al iniciar la consola de nuevo se crea un chat nuevo: la consola no retoma chats anteriores

Escenario: Consola cerrada de golpe
  Dado que la consola terminó sin "salir" y su chat quedó "en uso en la consola"
  Cuando selecciono "Liberar"
  Entonces el chat queda disponible para escribir desde la web

Escenario: Mensajes nuevos de otro canal
  Dado que tengo abierto el chat de una persona de WhatsApp
  Cuando la persona escribe
  Entonces en pocos segundos veo que su mensaje se está procesando
  Y al terminar el turno aparecen su mensaje y la respuesta sin recargar la página
  Y si estoy leyendo más arriba, se me avisa que hay mensajes nuevos en lugar de moverme

Escenario: Inactividad en todos los canales
  Dado un chat de web o consola cuyo hilo abierto lleva más de THREAD_IDLE_TIMEOUT_HOURS sin actividad
  Cuando escribo un mensaje nuevo
  Entonces ese hilo se cierra antes de procesar el mensaje, igual que en WhatsApp

Escenario: Histórico importado
  Dado que había hilos en archivos JSON de antes de la migración
  Cuando ejecuto la importación
  Entonces aparecen en un chat "Histórico" de solo lectura con sus mensajes, trazas y alertas
  Y ejecutar la importación otra vez no los duplica

Escenario: Mensajes fuera de alcance
  Cuando un mensaje completamente ajeno recibe el mensaje fijo de alcance
  Entonces no se guarda en el hilo y no aparece en la auditoría (HU-07)
```
Estado: 🔄 Aprobada (2026-10-18); en implementación. Implementada (fases 2 a 5) y probada automáticamente. Recorrido visual hecho con datos sintéticos (2026-10-18): chat de solo lectura, colores y separadores por hilo, carga hacia arriba, auditoría con alertas, liberar una consola, enviar desde la web, actualización automática y pantalla angosta. Falta el recorrido en el PC de pruebas con Ollama, la consola y WhatsApp reales. Reemplaza en parte a la HU-08
