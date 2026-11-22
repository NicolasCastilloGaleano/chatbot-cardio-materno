# ADR 0022: Escalamiento al profesional de salud cuando no hay evidencia

- **Estado:** Propuesto (2026-11-22). Las decisiones de producto las tomó Santiago Silva; falta la revisión del equipo y del equipo clínico
- **Fecha:** 2026-11-22
- **Decisores:** equipo del proyecto y equipo clínico. La IA propone; el equipo decide (AGENTS.md §5)
- **Modifica:** ADR 0010 (nunca se muestra una afirmación de salud sin respaldo verificable) y ADR 0016 (la web no escribe en chats de WhatsApp)
- **Relacionado:** ADR 0023 (dirección temporal de WhatsApp), HU-15 y `application/gaps.py` (vacíos), B-016 (aviso al equipo de salud)
- **Historia:** HU-16 (B-037)

## Contexto
Cuando la base no tiene información para orientar, el asistente responde con la abstención ("No tengo información validada…") o con el cierre honesto de la indagación, y la conversación termina ahí. El informe de vacíos (HU-15) muestra que esos casos existen: comida y presión arterial, ardor de estómago, dolor de brazo. La persona se queda sin respuesta, y nadie del equipo de salud se entera.

El usuario pidió (2026-11-22) que esos casos pasen a un **profesional de salud**, con un resumen clínico y una sugerencia de respuesta, y que el profesional pueda **aprobar**, **modificar** o abrir un **contacto directo**. Debe funcionar en el portal web y en WhatsApp, como en los chats de bancos u operadoras: la conversación pasa a un asesor dentro del mismo chat, sin exponer el teléfono del profesional.

Restricciones:
- **Las alarmas no pueden esperar a nadie** (ADR 0004 y 0007): el aviso de urgencia sale siempre de inmediato, sin modelo.
- **Ninguna afirmación de salud sin respaldo** (ADR 0010): un borrador del modelo sin evidencia no puede llegar a la persona por sí solo.
- **No hay autenticación** en el portal, que solo escucha en el propio equipo (ADR 0013).
- **El consentimiento (HU-01) está pendiente:** no se usa con personas reales.

## Decisión
1. **Cuándo se abre un caso.** Cuando el turno termina en la abstención por falta de información o en el cierre honesto, que son los vacíos de la HU-15, reconocidos con `gap_of`. **Nunca** cuando hubo una alarma, cuando el buscador no estaba disponible (es una falla técnica, no un vacío) ni en saludos. Un caso abierto por persona: un vacío nuevo se agrega al caso que ya tiene.
2. **Qué ve la persona.** En vez de la abstención, una plantilla fija: su consulta fue enviada a un profesional de salud, que le responderá en este mismo chat, y si empeora debe acudir a un servicio de salud. Si ya tiene un caso abierto, un recordatorio de que sigue en revisión.
3. **Qué recibe el profesional:**
   - **Resumen clínico** sin datos de identificación: dominio, resumen del hilo, síntomas y códigos reportados, consulta de búsqueda, motivo del vacío, categoría y similitud. Es lo que ya guarda la traza.
   - **La conversación del hilo,** porque la necesita para decidir. Es información de salud: por eso, hasta que exista la HU-01, solo con usuarios de prueba.
   - **Un borrador de respuesta** del modelo de respuesta, con su propio conocimiento, en un recuadro marcado **"sin respaldo de la base"**. Se genera cuando el profesional abre el caso, no en el turno de la persona, para no hacerla esperar. Recibe **solo el resumen**, nunca los mensajes, para no enviar datos personales al modelo (AGENTS.md §4). Si falla, el profesional escribe desde cero.
4. **Las tres acciones:**
   - **Aprobar:** el borrador se envía tal cual.
   - **Modificar:** el profesional lo edita y se envía su texto.
   - **Contacto directo:** el asistente se pausa para esa persona; sus mensajes nuevos van al profesional, sin llamar a ningún modelo, y el profesional responde desde el portal. Al cerrar el contacto, el asistente vuelve en el siguiente mensaje.
5. **Cambio al ADR 0010:** un texto aprobado o escrito por el profesional se considera respaldado por él. La responsabilidad clínica es suya, y el mensaje se muestra como **"Profesional de salud"**, nunca como del asistente.
6. **Las alarmas siguen primero, también durante el contacto directo.** El filtro 1 corre antes que el desvío: una urgencia sale con su aviso fijo y queda registrada en el caso, para que el profesional la vea.
7. **Estados del caso** (reglas puras en `domain/escalation.py`): `pendiente` → `aprobada` | `modificada` | `en_contacto` → `cerrada`; cualquier caso abierto pasa a `expirada` al vencer la ventana de 24 h (`ESCALATION_WINDOW_HOURS`).
8. **Rol nuevo `profesional`** en los mensajes del hilo. Antes de cualquier llamada al modelo se convierte en asistente, con el prefijo "Profesional de salud:", porque Ollama solo acepta los roles que conoce.
9. **Acceso del profesional:** una sola clave en el `.env` (`CLINICIAN_ACCESS_KEY`), enviada en un encabezado y comparada en tiempo constante. Sin clave, el apartado no existe. El portal sigue solo en el propio equipo. Se registra el actor como "profesional", sin nombres.
10. **Entrega por canal.** En los chats de consola y web, el mensaje del profesional se agrega al hilo y aparece con la consulta periódica que ya existe. En WhatsApp va por una **bandeja de salida** en la base compartida, que el proceso de WhatsApp envía con el número del proyecto; el profesional nunca usa su teléfono. Solo fluyen mensajes del profesional: la web sigue sin escribir como si fuera la persona (ADR 0016).
11. **Activación aparte:** `ESCALATION_MODE` (`apagado` por defecto, `observar` crea el caso pero mantiene la abstención, `activo`).

## Implementación
**Fase 1 (2026-11-22):** `domain/escalation.py` (estados y transiciones), el puerto `CaseRepository` acotado por persona, la tabla `clinical_cases` (esquema v3) y el gancho en `ConversationService.send`: con un vacío y sin alarma, `activo` pone el aviso de espera y abre el caso, o suma el turno al caso abierto. La fábrica de servicios ahora recibe el id de la persona. Aún no hay apartado del médico ni rol `profesional`: llegan en la fase 2, cuando existen sus mensajes. Las tablas de la dirección temporal y de la bandeja de salida llegan en la fase 4, para no crear tablas que todavía no se usan.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Sin borrador: el profesional escribe todo | Sin llamada extra al modelo | Más trabajo; el usuario eligió el borrador marcado |
| Generar el borrador en el turno de la persona | El caso llega completo | La persona espera más; en este PC, decenas de segundos |
| Enviar el borrador si nadie responde a tiempo | La persona siempre recibe algo | Es una afirmación sin respaldo ni revisión: contradice el ADR 0010 |
| Desviar también las alarmas al profesional | Un solo canal | Una urgencia no puede esperar a una persona que quizá no está |
| El proceso web envía directo por WhatsApp | Menos piezas | Las credenciales de WhatsApp en dos procesos; un envío fallido se pierde. La bandeja de salida reintenta |
| Cuentas por profesional | Se sabe quién respondió | Es un sistema de usuarios completo; queda para antes de un piloto |

## Consecuencias
- ✅ Los vacíos dejan de ser un callejón sin salida: la persona sabe que un profesional la atenderá.
- ✅ Se aprovecha lo que ya existe: `gap_of`, la traza, la auditoría, la consulta periódica de la web y el envío de WhatsApp.
- ⚠️ **No es apto para personas reales:** falta el consentimiento (HU-01), la clave es compartida y no hay registro de quién actuó.
- ⚠️ **Si el profesional no responde en 24 h,** WhatsApp no deja escribir sin plantilla aprobada, y la persona no recibe aviso. El mensaje de espera ya le indica acudir si empeora. Avisar al profesional cuando llega un caso queda para el B-016.
- ⚠️ El prompt del borrador y los textos de espera requieren revisión clínica.
- ⚠️ La web y WhatsApp escriben en la misma base: se usan transiciones optimistas y tomas atómicas de la bandeja de salida.
