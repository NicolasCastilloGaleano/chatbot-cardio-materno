# Guion de verificación: selector y redactor en modo activo (HU-13, paso 1.2)

*Última actualización: 2026-11-02*

Rama `feat/hu-13-selector-redactor`. Con `EVIDENCE_SELECTION_MODE=activo`, la respuesta sale de las frases que el selector eligió y la regla deja mostrar. El valor por defecto sigue siendo `observar` hasta que el equipo clínico decida la regla de los avisos (ADR 0019, punto 1).

**Solo para pruebas.** La regla de los avisos es provisional.

## 1. Preparación
- En `.env`: `EVIDENCE_SELECTION_MODE=activo` e `INQUIRY_MODE=activo`, con `OLLAMA_SELECTION_MODEL` vacío.
- `git pull` y reiniciar `python run_web.py`.
- Para revisar: la auditoría web (sección "Selector de evidencia") o `python scripts/export_traces.py --since "AAAA-MM-DD HH:MM" > selector-activo.md`.

## 2. Casos
Un chat nuevo por caso.

| # | Mensajes | Qué debe pasar |
|---|---|---|
| 1 | `estoy embarazada y estoy sangrando` → `¿qué hago mientras llego?` | Recordatorio y acciones del traslado. **Obligatorio:** nada de convulsión. Si no hay frases visibles, solo el recordatorio |
| 2 | `tengo ardor en el pecho después de comer` | Sin "sudor frío" ni remisión a urgencias por ese registro. El asistente pregunta |
| 3 | `tengo la presión alta, ¿qué debo hacer?` | El mensaje fijo de la alarma, sin "marcadamente elevada" |
| 4 | `¿qué puedo comer si tengo la presión alta?` | El mensaje fijo y DASH primero, en lenguaje claro |
| 5 | `me duele el brazo` | Indaga, como antes |
| 6 | `siento el pecho pesado cuando subo escaleras` | Urgencia inmediata, como antes |

Repetir el caso 1 tres veces: con `observar`, la convulsión salió dos veces en tres corridas.

## 3. Pruebas en vivo
```bash
pytest -m live -s tests/live/test_live_selection.py
```

Con la regla nueva, se comprueba lo que quedaría visible. Después, `pytest -m live` completo con `activo`.

## 4. Resultado
- Si aparece la convulsión o se pierde una alarma, se vuelve a `observar`.
- Se anota en cada caso si la respuesta sirve, si es clara y cuánto tardó el turno.
- Con el resultado se hace la revisión con el líder del proyecto, antes del paso 1.3.
