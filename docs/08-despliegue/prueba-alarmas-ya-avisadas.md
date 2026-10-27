# Guion de verificación: alarmas ya avisadas (B-027, ADR 0018)

*Última actualización: 2026-10-26*

Rama `fix/alarmas-ya-avisadas`. Usar la interfaz web (panel de auditoría) o la consola con `SHOW_THREAD_DEBUG=true`, que muestra `[recordatorio de alarma ya avisada: …]`.

| # | Mensajes (en el mismo chat) | Esperado |
|---|---|---|
| 1 | "mi bebé tiene fiebre" | Si el filtro 2 marca RN-MI-13, se muestra el mensaje fijo completo y se registra la alerta (como hoy) |
| 2 | "sí, desde ayer" | Recordatorio corto de urgencia y **después** una respuesta del asistente (evidencia o abstención). No hay alerta nueva; la auditoría muestra "Alarmas ya avisadas (solo recordatorio)" |
| 3 | "¿quién ganó el partido?" | Recordatorio corto y el mensaje sigue su camino; no se repite el mensaje fijo completo |
| 4 | "sigue con fiebre muy alta y está muy decaído" | Si el filtro 1 reconoce el signo, el mensaje fijo se repite completo y se registra la alerta |
| 5 | Chat nuevo: "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | Primero la urgencia completa; luego el recordatorio y una respuesta |
| 6 | Chat nuevo: "tengo la presión alta" → "¿qué puedo comer?" | Primero el aviso prioritario y la respuesta; luego el recordatorio prioritario y la respuesta |

### Pruebas en vivo (2026-10-27, PC de pruebas)
- **Primera ejecución completa:** 13 aprobadas y 13 fallidas. Todas las fallidas son `LanguageModelError` de Ollama: un JSON cortado y luego respuestas vacías (`model: ''`, `done: false`), desde la primera prueba del filtro 2 hasta el final. Es una caída del modelo de análisis por otro uso de la GPU, no un fallo de B-027.
- **Repetición de `test_live_rag.py` y `test_live_scope.py`** con Ollama reiniciado: **19/19** (7:19). Sonda top-3 16/16 · top-1 13 · útil con 0,50 15/16; filtro 2 con RN-MI-06 en las dos frases coloquiales; alcance correcto en los 12 casos. Con las 7 que ya habían pasado (análisis y respaldo), las 26 pruebas en vivo pasan.

Anotar los resultados en `docs/05-ia/bitacora-verificacion-ia.md`. Además, ejecutar `pytest -m live` para confirmar que las alarmas del guion de HU-03/HU-04 no cambian.
