# Guion de verificación: indagación en modo observar (HU-11, fase 2, ADR 0017)

*Última actualización: 2026-10-27*

Rama `feat/hu-11-indagacion`. En esta fase la regla de indagación **solo observa**:
- en cada turno sin alarma nueva calcula qué haría (responder, indagar, abstenerse o cerrar) y lo guarda en la traza;
- la respuesta es la misma que en `main`.

El objetivo es doble: confirmar que nada cambió y juntar trazas para calibrar los umbrales antes de activar la fase 3.

También entra el prompt de análisis v7, que agrega `about_health` y `wants_guidance` y cambia el alcance de un mensaje ajeno dentro de un hilo con síntomas (HU-07, ADR 0009).

## 1. Preparación
- `.env` con `INQUIRY_MODE=observar` (es el valor por defecto) y los `INQUIRY_*` vacíos, para usar los del archivo: piso 0,40, responder 0,60, margen 0,03, coincidencia 2, avance 0,02, máximo 3 turnos, 2 sin avance.
- Para ver la decisión de la regla, usar la interfaz web (sección "Indagación (HU-11, observada…)" de la auditoría) o la consola con `SHOW_THREAD_DEBUG=true`, que muestra `[indagación observada: …]`.

## 2. Pruebas en vivo
Ejecutar `pytest -m live -s` en la rama. Es obligatorio por el cambio de prompt de análisis.
- **Debe seguir igual que en `main`:** análisis, respaldo, sonda, filtro 2 y los 12 casos de alcance.
- **Dos casos nuevos de alcance:**
  - "¿quién ganó el partido?" en un hilo con fiebre debe quedar `fuera_de_alcance`;
  - "ya no quiero más preguntas, ¿qué hago?" debe tener `wants_guidance` verdadero.

| Resultado (PC de pruebas) | Rama |
|---|---|
| `pytest -m live` completo | |
| Partido en un hilo con fiebre | |
| Pedido directo de orientación | |

## 3. Guion manual: la respuesta no cambia y la regla se registra
| # | Mensajes (en el mismo chat) | Esperado |
|---|---|---|
| 1 | "¿por qué es importante controlar la presión si no me duele nada?" | La respuesta de siempre. La regla debería decir "responder" (evidencia clara) |
| 2 | Chat nuevo: "tengo un ardor raro" → la respuesta que dé el asistente → "es en el pecho, después de comer" | Respuestas como en `main`. En la auditoría, la regla probablemente diga "indagar" en el primer turno; en el segundo se ven el turno de indagación, el avance y si cambió el modo |
| 3 | Chat nuevo: "mi bebé tiene fiebre" → "sí, desde ayer" → "¿quién ganó el partido?" | El partido recibe el mensaje fijo de alcance, ya no la abstención. Si se avisó RN-MI-13, el recordatorio va antes. No queda en el hilo |
| 4 | En el chat 3: "ya no quiero más preguntas, ¿qué hago?" | La auditoría muestra "Pide orientación: Sí" y el modo "responder" si hay evidencia (≥ 0,50) |
| 5 | Chat nuevo: "hola" → "tengo la presión alta" → "gracias" | Los saludos siguen siendo conversacionales; la alarma prioritaria se muestra como siempre y en ese turno no hay sección de indagación |
| 6 | 5 a 10 conversaciones libres de temas variados, algunas vagas | Anotar, por turno, el modo de la regla, s1, el margen y la coincidencia, y si la decisión parece razonable. Sirve para calibrar |

### Resultados (2026-10-27, PC de pruebas)
- `pytest -m live`: 28/29. El partido en un hilo con fiebre quedó fuera de alcance y el pedido directo se detectó. Falló una vez el arrastre de "acidez" a un tema nuevo, pero la repetición dio 5/5: fue azar del modelo.
- Guion: la regla eligió bien en los casos claros: responder con s1 0,73-0,74 y coincidencia 3-4; indagar con "tengo un ardor raro" (0,49); responder con el pedido directo (0,66).
- Hallazgos corregidos el mismo día en la rama:
  - la web escondía el saludo sin hilo y dibujaba al final el mensaje fuera de alcance;
  - "gracias" en un hilo salía "indagar";
  - la respuesta a la abstención abría un hilo nuevo;
  - el análisis llenaba el contexto de 4096 y la web respondía 502.
- Pendiente: repetir `pytest -m live` (prompt v7 ajustado y prueba nueva), comprobar en la web los turnos sin guardar, medir el análisis con 8192 y hacer más conversaciones vagas para calibrar.

## 4. Calibración
Con las trazas del punto 3, revisar:
- **Responder sin indagar:** ¿los turnos con evidencia clara superan 0,60 con margen o coincidencia?
- **Indagar:** ¿los mensajes vagos caen entre 0,40 y 0,60?
- **Cerrar:** ¿hay turnos que cerrarían habiendo información útil?

Si un umbral no corresponde, se ajusta en `.env` (`INQUIRY_*`), y el valor nuevo se pasa a `knowledge/evidence_policy.json` cuando el equipo lo apruebe.

Para pasar los resultados sin copiar desde la auditoría: `python scripts/export_traces.py --since "AAAA-MM-DD HH:MM" > trazas.md` (hora local de inicio del guion) y compartir ese archivo. Ver `docs/08-despliegue/operacion.md`.

Anotar los resultados en `docs/05-ia/bitacora-verificacion-ia.md`.
