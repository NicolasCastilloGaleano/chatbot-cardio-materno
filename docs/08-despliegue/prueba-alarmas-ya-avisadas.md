# Guion de verificación: alarmas ya avisadas (B-027, ADR 0018)

*Última actualización: 2026-10-27*

Rama `fix/alarmas-ya-avisadas`. Usar la interfaz web (panel de auditoría) o la consola con `SHOW_THREAD_DEBUG=true`, que muestra `[recordatorio de alarma ya avisada: …]`.

| # | Mensajes (en el mismo chat) | Esperado |
|---|---|---|
| 1 | "mi bebé tiene fiebre" | Si el filtro 2 marca RN-MI-13, se muestra el mensaje fijo completo y se registra la alerta (como hoy) |
| 2 | "sí, desde ayer" | Recordatorio corto de urgencia y **después** una respuesta del asistente (evidencia o abstención). No hay alerta nueva; la auditoría muestra "Alarmas ya avisadas (solo recordatorio)" |
| 3 | "¿quién ganó el partido?" | Recordatorio corto y el mensaje sigue su camino; no se repite el mensaje fijo completo |
| 4 | "sigue con fiebre muy alta y está muy decaído" | Si el filtro 1 reconoce el signo, el mensaje fijo se repite completo y se registra la alerta |
| 5 | Chat nuevo: "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | Primero la urgencia completa; luego el recordatorio y una respuesta |
| 6 | Chat nuevo: "tengo la presión alta" → "¿qué puedo comer?" | Primero el aviso prioritario y la respuesta. Luego, **solo si el filtro 2 vuelve a encontrar la regla**, el recordatorio prioritario y la respuesta; si no la encuentra, solo la respuesta (ADR 0018, punto decidido 1) |

### Pruebas en vivo (2026-10-27, PC de pruebas)
- **Primera ejecución completa:** 13 aprobadas y 13 fallidas. Todas las fallidas son `LanguageModelError` de Ollama: un JSON cortado y luego respuestas vacías (`model: ''`, `done: false`), desde la primera prueba del filtro 2 hasta el final. Es una caída del modelo de análisis por otro uso de la GPU, no un fallo de B-027.
- **Repetición de `test_live_rag.py` y `test_live_scope.py`** con Ollama reiniciado: **19/19** (7:19). Sonda top-3 16/16 · top-1 13 · útil con 0,50 15/16; filtro 2 con RN-MI-06 en las dos frases coloquiales; alcance correcto en los 12 casos. Con las 7 que ya habían pasado (análisis y respaldo), las 26 pruebas en vivo pasan.

### Guion manual (2026-10-27, PC de pruebas, interfaz web)
| # | Resultado | Valoración |
|---|---|---|
| 1 | RN-MI-13 con el mensaje fijo completo | ✅ Como hoy. Sigue el exceso de códigos ("mi bebé" sin edad → recién nacido), grupo C |
| 2 | Recordatorio de urgencia y después una respuesta con evidencia que pide edad, temperatura y signos | ✅ El caso clave: la conversación ya no queda bloqueada |
| 3 | Recordatorio y abstención ("¿Me puedes contar con otras palabras qué sientes…?"), guardada en el hilo; el resumen del hilo menciona el partido | ✅ Para B-027. ⚠️ Hallazgo aparte: como el análisis acumula los síntomas del hilo, `effective_scope` lo deja en alcance y no sale el mensaje fijo de fuera de alcance |
| 4 | Regla nueva RN-MI-11 con el mensaje fijo completo, sin recordatorio de RN-MI-13 | ✅ Regla nueva → comportamiento de siempre |
| 5 | Urgencia completa; luego el recordatorio y un texto literal de un registro de sangrado tras relaciones | ✅ Para B-027. ⚠️ La evidencia no corresponde a "¿qué hago mientras llego?" (cobertura de la base y elección del literal) |
| 6 | Aviso prioritario RN-CV-06 y respuesta; luego solo la respuesta sobre alimentación (DASH, sodio), sin recordatorio | ✅ Según el ADR 0018: el filtro 2 no volvió a encontrar la regla. El guion decía "recordatorio" sin esa condición y se corrigió. ⚠️ La primera respuesta habla de molestia en el pecho, que la persona no mencionó |

**Conclusión:** B-027 se comporta según el ADR 0018 en los 6 casos. Los hallazgos ⚠️ no son de B-027 y quedan para después: alcance en hilos con síntomas acumulados, evidencia poco pertinente y exceso de códigos (grupo C).

Anotar los resultados en `docs/05-ia/bitacora-verificacion-ia.md`. Además, ejecutar `pytest -m live` para confirmar que las alarmas del guion de HU-03/HU-04 no cambian.
