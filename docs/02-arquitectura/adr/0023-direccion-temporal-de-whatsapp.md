# ADR 0023: Dirección temporal de WhatsApp mientras hay un caso abierto

- **Estado:** Propuesto (2026-11-22). La decisión de producto la tomó Santiago Silva; falta la revisión del equipo
- **Fecha:** 2026-11-22
- **Decisores:** equipo del proyecto. La IA propone; el equipo decide (AGENTS.md §5)
- **Modifica:** ADR 0015 (solo se guarda el HMAC del número; el número vive solo en memoria)
- **Relacionado:** ADR 0014 (canal WhatsApp), ADR 0022 (escalamiento al profesional)
- **Historia:** HU-16 (B-037)

## Contexto
Hoy el número de WhatsApp de la persona (`wa_id`) solo existe en memoria mientras se atiende su mensaje (`IncomingMessage.reply_to`). En la base se guarda un HMAC con `USER_ID_HASH_SECRET`, que no se puede revertir. Así, el sistema solo puede responder a un mensaje que acaba de llegar.

Con el escalamiento (ADR 0022), el profesional responde minutos u horas después, cuando el mensaje de la persona ya se procesó. Sin una dirección guardada, esa respuesta no tiene a dónde ir.

WhatsApp permite mensajes libres solo dentro de las **24 h** siguientes al último mensaje de la persona. Después exige plantillas aprobadas por Meta, que el proyecto no tiene.

## Decisión
1. **Se guarda el `wa_id` solo mientras hay un caso abierto**, en una tabla aparte (`case_addresses`), ligada al caso y no a la persona.
2. **Vence a las 24 h** del último mensaje de la persona. Cada mensaje nuevo de ella, con el caso abierto, renueva el vencimiento, porque WhatsApp también reinicia la ventana.
3. **Se borra** al cerrar el caso, al vencer o si el caso pasa a `expirada`. Una tarea periódica del proceso de WhatsApp purga las direcciones vencidas.
4. **Nunca se guarda el nombre** del perfil ni otros datos, y el número no aparece en la auditoría, en el informe de vacíos, en los registros de la aplicación ni en el portal del profesional.
5. **El HMAC sigue siendo la identidad** de la persona (ADR 0015). La dirección temporal solo sirve para entregar mensajes del profesional.
6. **Sin dependencias nuevas.** No se cifra con una clave propia: se decidió guardar lo mínimo, por el menor tiempo, en lugar de agregar manejo de claves. La protección de la base (archivo local, fuera del repositorio) es la misma de hoy.

## Implementación (fase 4 de la HU-16, 2026-11-22)
- **Esquema v4:** `case_addresses` (caso, persona, `reply_to`, actualización) y `clinician_outbox` (mensajes del profesional pendientes de envío).
- **Cuándo se guarda:** solo si el caso está abierto y la persona recibió el aviso (`notified = 1`); un caso en modo `observar` nunca guarda la dirección. El vencimiento es el del caso, que cada mensaje de la persona renueva.
- **Cuándo se borra:** en cada vuelta del reenvío, la dirección de un caso cerrado o vencido se borra en cuanto no le queda nada por enviar. Lo pendiente de un caso vencido se marca `fallido` (`ventana_cerrada`).
- **El texto del profesional** se borra de la bandeja apenas se envía o falla; queda solo en el hilo de la persona.
- **El número** no sale de `case_addresses`: no se registra, no se muestra en `/medico` ni en la auditoría.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Guardar el número cifrado | Más protección si se copia la base | Dependencia nueva (`cryptography`, exige ADR) y manejo de claves |
| Solo en memoria | No se guarda nada | Si se reinicia el servicio, el profesional ya no puede responder |
| Guardarlo siempre, con la persona | Permite avisos futuros (B-016) | Más datos personales por más tiempo, sin necesidad actual |

## Consecuencias
- ✅ El profesional puede responder por el mismo chat sin conocer el número.
- ✅ El número se guarda por un tiempo acotado y con un propósito único.
- ⚠️ **Es un dato personal** guardado en la base, aunque sea temporal: hay que actualizar la protección de datos (`docs/07-gobernanza/proteccion-datos.md`) y tenerlo en el consentimiento (HU-01) antes de cualquier persona real.
- ⚠️ Si el caso vence sin respuesta, no hay forma de avisarle a la persona por WhatsApp.
