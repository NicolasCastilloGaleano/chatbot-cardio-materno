# Guion de verificación: selector de evidencia en modo observar (HU-13, paso 1.1)

*Última actualización: 2026-11-01*

Rama `feat/hu-13-selector-redactor`. Con `EVIDENCE_SELECTION_MODE=observar`, antes de redactar corre el selector de evidencia. Su resultado **solo va a la traza**: la respuesta debe ser la misma de la línea base, salvo lo que cambia entre dos corridas del modelo.

Este guion decide si se construye el redactor (paso 1.2). La línea base está en el [ADR 0019](../02-arquitectura/adr/0019-selector-de-evidencia-y-redactor-supervisor.md).

## 1. Preparación
- `.env` con `EVIDENCE_SELECTION_MODE=observar` (es el valor por defecto), `OLLAMA_SELECTION_MODEL` vacío (usa el modelo del análisis) e `INQUIRY_MODE=activo`.
- Las líneas `KB_*` de la base v2, comentadas.
- `git fetch`, `git checkout feat/hu-13-selector-redactor`, `git pull` y reiniciar `python run_web.py`.
- Para revisar: la auditoría web (sección "Selector de evidencia") o `python scripts/export_traces.py --since "AAAA-MM-DD HH:MM" > selector-observar.md`.

## 2. Casos
Un chat nuevo por caso.

| # | Mensajes | Qué debe elegir el selector | Para aprobar |
|---|---|---|---|
| 1 | `estoy embarazada y estoy sangrando` → `¿qué hago mientras llego?` | Frases del sangrado, o `no_responde` | **Obligatorio:** nada de las instrucciones de una convulsión ("protege la cabeza", "no sujetes sus movimientos") |
| 2 | `tengo ardor en el pecho después de comer` | Lo que dice del reflujo y del ardor | Sin "sudor frío" entre las elegidas. Anotar si el aviso de urgencias aparece como "aviso que agregaría" |
| 3 | `tengo la presión alta, ¿qué debo hacer?` | Qué hacer con la presión alta | Nada de "la molestia en el pecho" |
| 4 | `¿qué puedo comer si tengo la presión alta?` | Alimentación, con DASH entre las primeras | Primero lo que responde a la pregunta |
| 5 | `me duele el brazo` | No corre: el turno indaga | Sin sección del selector |
| 6 | `siento el pecho pesado cuando subo escaleras` | No corre: urgencia inmediata | Sin sección del selector; la alarma sale igual |

## 2.1. Prueba con evidencia fija
La búsqueda cambia entre corridas: el caso 1 puede no traer el registro de convulsión, y entonces no prueba nada. Esta prueba fija los registros, y es la que decide el caso 1:

```bash
pytest -m live -s tests/live/test_live_selection.py
```

Se repite 5 veces. En el caso del sangrado debe salir el traslado y ninguna frase de la convulsión.

## 3. Qué anotar para el equipo clínico
En cada caso con selector, la traza muestra dos listas (ADR 0019, punto 1):
- **avisos que agregaría:** avisos de los registros elegidos que el selector no eligió;
- **avisos por fuera:** avisos de los registros que no eligió.

Hay que marcar cuáles debían mostrarse. Con eso, el equipo clínico decide la regla de los avisos antes del paso 1.2.

## 4. Resultado
- Si el caso 1 falla, se ajusta el prompt del selector y se repite. No se pasa al paso 1.2.
- Si la selección es útil en los casos 1 a 4, se sigue con el redactor.
- Si `selector observado: falló` aparece seguido, se revisa la causa antes de seguir.

Lo que se registre aquí queda en la bitácora.
