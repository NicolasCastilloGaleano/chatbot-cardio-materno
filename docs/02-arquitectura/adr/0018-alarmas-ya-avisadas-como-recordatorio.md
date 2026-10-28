# ADR 0018: Una alarma ya avisada en el hilo se recuerda, no se repite completa

- **Estado:** Aceptado (2026-10-26), con las propuestas por defecto
- **Fecha:** 2026-10-26
- **Decisores:** equipo del proyecto (Nicolas Castillo Galeano y equipo clínico para los textos del recordatorio)
- **Modifica:** ADR 0007 (doble filtro de alarmas) y ADR 0012 (códigos cerrados): cambia cómo se muestra una regla que el filtro 2 vuelve a encontrar en el mismo hilo. No cambia el catálogo ni las reglas.
- **Historias:** HU-03 y HU-04 (B-027). Requisito previo de la HU-11 (ADR 0017).

## Contexto
En el guion manual de B-025 (2026-10-26, PC de pruebas) se vio esto:
- "mi bebé tiene fiebre" activó RN-MI-13 (urgencia inmediata);
- en el mismo hilo, "sí, desde ayer" y "¿quién ganó el partido?" volvieron a recibir el mismo mensaje fijo de urgencia, completo.

La causa es de diseño, no del catálogo. El prompt de análisis v6 pide que `reported_symptoms` incluya lo dicho antes en el hilo ("no omitas ninguno"), para que el filtro 2 combine el contexto ("tengo 34 semanas") con el signo nuevo. Pero eso hace que, una vez detectada una regla, el filtro 2 la encuentre de nuevo **en cada turno**.

Con una urgencia, la conversación queda bloqueada: el asistente solo repite el aviso, no busca evidencia, no responde y, con la HU-11, tampoco podría indagar. Repetir el mismo texto en cada turno además le resta fuerza al aviso.

Se observó un segundo problema, que este ADR **no** resuelve: el filtro 2 asigna códigos que la persona no dijo ("mi bebé" sin edad → "recién nacido"; acidez → "dolor en el pecho"). Corresponde a las correcciones del grupo C (puerta P3: fragmento textual de cada código y retiro del puente de nombres) y se tratará aparte.

## Decisión
1. **Regla ya avisada:** una regla cuyo identificador aparece en las alertas registradas del **hilo activo** (`ThreadRepository.all_alerts`).
2. **Filtro 1 (texto de la persona), sin cambios:** si el mensaje nuevo vuelve a describir el signo, la alarma se muestra completa y se registra, aunque ya se haya avisado. La persona lo está volviendo a decir.
3. **Filtro 2 con una regla ya avisada:**
   - no se repite el mensaje fijo ni se registra una alerta nueva;
   - la respuesta empieza con un **recordatorio fijo y corto** según la gravedad;
   - el turno sigue su camino normal: alcance, evidencia y respuesta (o indagación, con la HU-11);
   - la traza guarda las reglas recordadas (`reminded_rules`), que se ven en la auditoría web y en la consola.
4. **Regla nueva en el hilo, por cualquiera de los dos filtros:** se comporta exactamente como hoy, con el mensaje fijo completo, la alerta registrada y, si es una urgencia inmediata, sin RAG ni respuesta.
5. **El recordatorio nunca se pierde:** aparece también si el mensaje es fuera de alcance, conversacional o termina en abstención. El alcance nunca suprime una alarma (ADR 0009).
6. **Alcance de "ya avisada":** solo el hilo activo. Un hilo nuevo, o el hilo siguiente al cierre por inactividad, evalúa todo desde cero.
7. **Textos propuestos** (los aprueba el equipo clínico; van como constantes, no en el catálogo):
   - urgencia: "⚠️ Recuerda lo que te indiqué: por lo que me contaste, lo indicado es acudir al servicio de urgencias más cercano o llamar a la línea 123.";
   - prioritaria: "⚠️ Recuerda lo que te indiqué: por lo que me contaste, conviene que consultes pronto con el personal de salud.".
8. **Lugar del código:** la regla de "ya avisada" es determinista y vive en `application/alarm_policy.py`, junto a `compose_reply`. El LLM no interviene.

## Puntos decididos (2026-10-26, Nicolas Castillo Galeano)
- El recordatorio aparece **en cada turno** en que el filtro 2 vuelve a encontrar la regla.
- Después de recordar una urgencia **se permite indagar** (HU-11), con el recordatorio siempre primero.
- Los textos del recordatorio son los propuestos en el punto 7 (pendiente la revisión del equipo clínico, como todo el catálogo PROVISIONAL).

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Que el análisis reporte solo los síntomas del mensaje nuevo (prompt v7) | Corta la repetición en el origen | Pierde el contexto que hoy activa reglas correctas ("34 semanas" dicho antes + "sangrado" ahora). Depende del LLM y es riesgoso para el recall |
| No volver a alarmar una regla ya avisada, sin ningún recordatorio | Conversación limpia | Un aviso de urgencia desaparece en los turnos siguientes; inseguro |
| Repetir el mensaje fijo completo (actual) | Máxima insistencia | Bloquea la conversación y desgasta el aviso; observado en el PC |
| **Recordatorio corto y el turno sigue (elegida)** | El aviso se mantiene visible y la conversación puede avanzar | Una alarma falsa del filtro 2 deja un recordatorio en cada turno hasta que se corrija el exceso de códigos (grupo C) |

## Consecuencias
- ✅ Después de una alarma, la persona puede seguir conversando y recibir orientación con evidencia, sin perder el aviso.
- ✅ La auditoría distingue las alertas nuevas de los recordatorios. Las alertas registradas reflejan solo las detecciones nuevas.
- ✅ Requisito previo cumplido para la HU-11: la indagación ya no queda bloqueada en los hilos con una alarma.
- ⚠️ Si la persona vuelve a describir el signo con palabras que el filtro 1 no reconoce, solo verá el recordatorio y no el mensaje completo. El recordatorio mantiene la indicación de urgencia, así que se acepta.
- ⚠️ No corrige los códigos que el filtro 2 asigna de más. Ese queda como siguiente trabajo (grupo C, puerta P3).
- Pruebas previstas: unitarias en `test_conversation_service.py` y `test_alarm_policy` (o el archivo equivalente), y frases en `tests/conversational/` con el caso del bebé con fiebre seguido de "sí, desde ayer".

## Actualización 2026-10-28: acompañamiento de una urgencia recordada (B-030, especificación)
**Contexto.** Con el recordatorio (B-027), la persona ya no queda sola después de una urgencia. Pero en el guion de la HU-11 (2026-10-27), "¿voy directamente a urgencias?" después de RN-CV-01 recibió el recordatorio y luego un texto literal con preguntas sobre el esfuerzo. Esas preguntas estorban cuando lo indicado es salir ya. Nicolas Castillo Galeano decidió que el acompañamiento se mantiene y se afina: lo que sigue al recordatorio debe ser lo más útil para la urgencia.

**Decisión.** Reemplaza, **solo para las reglas de urgencia inmediata**, el punto decidido "después de recordar una urgencia se permite indagar":
1. Con una regla de urgencia inmediata solo recordada, el turno no indaga (la regla de la HU-11 no se aplica).
2. La llamada de respuesta recibe un contexto fijo de **URGENCIA EN CURSO**: priorizar, con la evidencia, qué hacer mientras la persona llega, qué llevar o decir al llegar y qué evitar; sin preguntas de caracterización ni diagnósticos.
3. Determinista: en ese turno se quitan las frases con pregunta, tanto de la redacción como del texto literal (B-028). Lo que se muestra sigue verificado (ADR 0010).
4. Sin evidencia pertinente, la respuesta es solo el recordatorio, sin la abstención que pide detalles.
5. Las reglas prioritarias recordadas siguen como en el punto decidido original: el turno puede indagar o responder.
6. La traza marca el acompañamiento de la urgencia, que se ve en la auditoría y en la exportación.

**Consecuencias.**
- ✅ Después de una urgencia, la conversación sigue y se orienta a la acción.
- ⚠️ La base tiene pocos registros sobre qué hacer mientras se llega (p. ej., el sangrado en el embarazo, guion de B-028). En esos casos sale solo el recordatorio, hasta que el equipo clínico amplíe la base (B-019).
- ⚠️ El contexto URGENCIA EN CURSO es un texto nuevo que debe revisar el equipo clínico.

