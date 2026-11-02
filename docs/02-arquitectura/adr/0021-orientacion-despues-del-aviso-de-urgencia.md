# ADR 0021: Orientación después del aviso de urgencia

- **Estado:** Aceptado (2026-11-02, decisión del equipo informada por Santiago Silva), con las propuestas de la sección "Puntos por decidir". Implementación pendiente
- **Fecha:** 2026-11-02
- **Decisores:** equipo del proyecto y equipo clínico (puerta P4). La IA propone; el equipo decide (AGENTS.md §5)
- **Modifica:** ADR 0007 (`urgencia_inmediata` solo mostraba el mensaje fijo) y ADR 0018 (el acompañamiento solo existía si la persona volvía a escribir)
- **Depende de:** HU-13 y ADR 0019 en modo `activo`
- **Historia:** HU-03 y HU-04 (B-034)

## Contexto
Ante una urgencia inmediata, el asistente muestra un mensaje fijo y termina el turno. Lo útil para ese momento solo aparece si la persona vuelve a escribir, por ejemplo "¿qué hago mientras llego?" (B-030). El usuario señaló el 2026-11-02 que eso no es lógico en una emergencia: la persona no debería tener que preguntar, y la solución debe ser general, sin textos por alarma.

Hay dos restricciones:
- **El aviso no puede esperar.** Hoy, el filtro 1 responde sin llamar a ningún modelo. Buscar, seleccionar y redactar tarda decenas de segundos.
- **Solo se puede decir lo que está en la base** (ADR 0010). Y sin el selector, la evidencia puede ser de otra emergencia: en las pruebas del 2026-11-01 y 2026-11-02, un sangrado recibió instrucciones de una convulsión.

## Decisión
**Dos mensajes.** Decisión del usuario (2026-11-02): el aviso sale primero y la orientación llega después, sin que la persona escriba.

1. **El aviso no cambia.** El mensaje fijo sale como hoy, con el mismo tiempo, se guarda y registra su alerta. Nada de lo que sigue puede retrasarlo, cambiarlo ni impedirlo.
2. **Orientación automática.** Después de una urgencia inmediata **nueva**, se reutiliza el acompañamiento: buscar, seleccionar y redactar con URGENCIA EN CURSO. Es el mismo camino para todas las alarmas: **no hay textos ni ramas por regla**.
3. **Solo con el selector en `activo`.** Sin él no hay segundo mensaje: no se usa el flujo anterior, porque es el que puede traer otra emergencia.
4. **Si no hay nada útil, no se dice nada.** Con `no_responde`, sin frases visibles, si falla una llamada o si la verificación no pasa, no hay segundo mensaje. La persona ya tiene el aviso. La traza lo registra, y esos casos alimentan el registro de vacíos (B-032). No se usa el texto literal: en una urgencia solo se muestra lo verificado. No se hacen preguntas.
5. **El segundo mensaje es un turno del asistente en el mismo hilo,** con su traza (`urgent_follow_up`), sin alerta nueva.
6. **Activación aparte:** `URGENT_GUIDANCE_MODE` (`apagado` por defecto, `activo`).

### Por canal
| Canal | Cómo llega el segundo mensaje |
|---|---|
| Consola | Se imprime el aviso y, después, la orientación |
| WhatsApp | El trabajador envía el aviso y luego la orientación; los mensajes nuevos esperan en la cola |
| Web | La solicitud responde con el aviso; la orientación corre en segundo plano y aparece con la consulta periódica que ya existe |

El servicio separa las dos partes: `send` devuelve el aviso e indica si hay orientación pendiente, y un método aparte la produce. Así, cada canal decide cuándo llamarlo. Se debe impedir que un mensaje nuevo y la orientación escriban a la vez en el mismo hilo.

## Puntos decididos (2026-11-02: se adoptan las propuestas)
1. **Aprobación clínica (P4):** ¿se permite mostrar orientación verificada después del aviso de una urgencia? Modifica el ADR 0007.
2. **Consulta de búsqueda.** Con el filtro 1 no hay análisis. **Propuesta:** buscar con el mensaje de la persona y el signo de la regla, sin análisis, y armar el CASO con esos datos. Se estiman 40 s en vez de 100 s. Con el filtro 2 ya hay análisis y se reutiliza.
3. **Frase de entrada.** ¿La orientación lleva un texto fijo, como "Mientras llegas:"? **Propuesta:** sí, como plantilla, con revisión clínica.
4. **Silencio cuando no hay contenido.** ¿Es aceptable no enviar nada? **Propuesta:** sí, porque el aviso ya dio la instrucción principal y un texto vacío de contenido no ayuda.
5. **Alcance de "nueva".** **Propuesta:** solo la primera vez por regla en el hilo. Después, sigue el acompañamiento actual si la persona escribe.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Un solo mensaje, con la orientación incluida | Es un solo texto | La persona esperaría decenas de segundos antes de ver "ve a urgencias" |
| Textos fijos por alarma | Rápido y revisable | Es contenido escrito en código, por cada regla; el usuario pidió una solución general |
| Dejar que el LLM oriente con su conocimiento | Siempre tendría algo que decir | Afirmaciones de salud sin respaldo (ADR 0010), en el peor momento |
| Mantener solo el acompañamiento actual | Sin cambios | La persona debe preguntar en plena emergencia |

## Consecuencias
- ✅ La persona recibe qué hacer sin preguntar, y el aviso llega igual de rápido.
- ✅ Funciona para cualquier alarma con contenido en la base, sin textos por regla.
- ⚠️ Hoy la base puede no traer lo más útil para el momento (por ejemplo, posición o qué evitar). Lo decide y lo escribe el equipo clínico; ningún agente lo inventa.
- ⚠️ Mientras llega la orientación, la persona podría estar saliendo o escribiendo. Debe seguir siendo un complemento, nunca algo que la haga esperar. El aviso no debe sugerir que viene más información.
- ⚠️ Agrega trabajo en segundo plano en la web y un paso más en cada canal.
- ⏳ Pendiente: implementación y revisión clínica del texto de la frase de entrada.
