# Guía del profesional de salud: casos escalados (HU-16)

*Última actualización: 2026-11-22*

Esta guía es para la persona del equipo de salud que atiende los casos que el asistente no pudo responder. Describe el prototipo: **solo se usa con usuarios de prueba** hasta que estén el consentimiento (HU-01), la validación clínica del borrador y una autenticación real (ADR 0022).

## 1. Qué es un caso
Cuando la base de conocimiento no tiene información para orientar a una persona, el asistente no inventa una respuesta. Le avisa que **un profesional de salud está revisando su consulta** y que, si empeora, acuda a urgencias o llame al 123. Ese turno abre un **caso** para ti.

Nunca se abre un caso por una alarma: las alarmas tienen su propio aviso inmediato, antes y durante el caso.

Un caso dura **24 horas desde el último mensaje de la persona**. Si nadie lo atiende en ese tiempo, vence y desaparece de la lista.

## 2. Entrar
1. Abre `http://127.0.0.1:8000/medico` en el equipo donde corre la interfaz (no funciona desde otro equipo).
2. Escribe la clave del profesional. Te la da quien administra el equipo; es la variable `CLINICIAN_ACCESS_KEY` del `.env`. **No la compartas.**
3. La clave se recuerda mientras la pestaña esté abierta. **Salir** la borra.

## 3. Revisar un caso
La lista de la izquierda muestra los casos abiertos, del más antiguo al más nuevo, con el canal (Web, Consola o WhatsApp) y cuándo vencen. Al abrir uno ves:
- **Resumen clínico:** motivo, dominio, resumen, síntomas y signos que el sistema entendió. No tiene datos de identificación.
- **Conversación:** los últimos mensajes de la persona, del asistente y tuyos.
- **Respuesta:** la nota para ti, el borrador y las acciones.

## 4. Tres formas de responder
| Acción | Cuándo usarla | Qué pasa |
|---|---|---|
| **Generar borrador** y luego **Aprobar borrador** | El borrador del modelo te parece correcto tal cual | La persona recibe ese texto. El caso se cierra |
| **Enviar mi versión** | Quieres corregir el borrador o escribir desde cero | La persona recibe tu texto. El caso se cierra |
| **Contacto directo** | Necesitas preguntarle algo o conversar | Se abre un chat. El caso sigue abierto hasta que pulses **Cerrar contacto** |

**El borrador no tiene respaldo de la base.** Lo escribe el modelo a partir del resumen y está marcado así. Léelo completo antes de aprobarlo: no debe tener diagnósticos, medicamentos ni dosis. Si lo editas, el botón Aprobar se desactiva y tienes que usar **Enviar mi versión**.

**La nota es solo para ti.** Al generar el borrador, el modelo escribe también una nota con posibles explicaciones a considerar, qué conviene preguntar o confirmar y qué signos de alarma descartar. Es una propuesta sin respaldo de la base, no un diagnóstico: úsala como lista de verificación. La nota **nunca se envía** a la persona. El resumen que recibe el modelo puede traer datos que solo se le preguntaron a la persona; revísalo con la conversación.

## 5. Contacto directo
- La persona lee tus mensajes en su mismo chat como **"Profesional de salud"**. En WhatsApp salen desde el número del proyecto, así que **tu número nunca se muestra**.
- Mientras dure el contacto **el asistente no le responde**: lo que escriba la persona aparece en la conversación del caso (se actualiza cada 5 segundos).
- **Las alarmas siguen funcionando:** si la persona escribe un signo de alarma reconocido por palabras clave, recibe el aviso de urgencia de inmediato y la alerta aparece en la conversación.
- **Importante:** durante el contacto el modelo no analiza los mensajes, así que una alarma descrita con palabras poco comunes **depende de que tú la leas**. Ante cualquier duda, indica acudir a urgencias o llamar al 123.
- `Ctrl + Enter` envía. **Cerrar contacto** le devuelve la conversación al asistente.

## 6. WhatsApp: ventana cerrada
WhatsApp solo deja escribirle a una persona hasta 24 horas después de su último mensaje. Si ves **"Ventana cerrada"**, no se le puede escribir: pasó ese tiempo o el número no quedó guardado. Si la persona vuelve a escribir, la ventana se abre de nuevo.

Tus mensajes de WhatsApp salen unos segundos después de enviarlos, siempre que el canal esté encendido.

## 7. Qué no hacer
- No escribas tu número, tu correo ni datos de otras personas.
- No pidas a la persona su documento, dirección ni otros datos de identificación.
- No diagnostiques ni formules por este medio: es **teleorientación** (Res. 2654 de 2019).
