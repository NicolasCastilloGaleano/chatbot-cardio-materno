# Base de conocimiento (RAG)

`entries.jsonl` contiene **1.600 registros** pregunta/respuesta, uno por línea:
`{id, domain, category, focus, question, answer}`.

| Dominio | Categorías | Enfoques |
|---|---|---|
| `cardiovascular` | 8 × 100 registros | *Indagar* (400): qué preguntar y qué señales importan · *Solucionar* (400): orientación |
| `materno_infantil` | 8 × 100 registros | ídem |

## Origen y estado de validación
- **Origen:** generado con IA (ChatGPT Work) con trabajo intensivo por categoría y búsqueda de fuentes. Se mantenía en un Google Spreadsheet del equipo y se sincronizaba con `kb_sync` en el piloto anterior (`piloto-agente-nanomaterno-cardiovascular`). Se exportó el 2026-10-10 con `scripts/export_pilot_kb.py`, conservando el `id` (hash) del piloto.
- **Estado: `VALIDADA_PARA_PROTOTIPO`.** Decisión acordada con **Miguel, líder del proyecto** (TODO: apellido), el 2026-10-10: se usa en el prototipo como datos validados.
- **Limitación:** los registros no tienen fuente, revisor ni fecha individuales. Para usar el asistente con usuarios reales se requiere la validación clínica (B-019: columnas Fuente/Validado por/Fecha en la hoja).

## Índice vectorial (derivado, no versionado)
El índice se genera desde este archivo y **no se sube a git** (`data/kb_index/`):
```bash
.venv/bin/python run_build_kb_index.py
```
Usa `OLLAMA_EMBED_MODEL` (por defecto `qwen3-embedding:8b`). Si este archivo o el modelo cambian, el asistente avisa al arrancar y hay que reconstruir el índice.

## Política de evidencia y verificación del respaldo
`knowledge/evidence_policy.json` define la búsqueda (umbral, `top_k`…; desde la v1.2.0, del 2026-10-12, el umbral es **0,50** por decisión del equipo) y, desde el ADR 0010, la verificación determinista de cada frase: `min_support` (0,6), `max_free_sentences` (2) y `max_free_words` (20). Los umbrales también se pueden fijar en `.env` (`RAG_MIN_SIMILARITY`, `RAG_TOP_K`, `RAG_CANDIDATE_K`, `GROUNDING_*`), que tienen prioridad sobre el archivo. Cambiar estos valores no obliga a reconstruir el índice, pero sí a repetir `pytest -m live` (`test_live_grounding.py` mide cuántas respuestas terminan en texto literal).

**Efecto de la verificación:** una pregunta que la base no cubre (p. ej., qué comer con acidez o la dosis de insulina en la diabetes gestacional) recibe la abstención o el texto literal de un registro *Indagar*. Llenar esos vacíos es contenido clínico (B-019).

## Base v2 (propuesta, aún no cargada)
La base v2 ([ADR 0017](../../docs/02-arquitectura/adr/0017-base-de-conocimiento-v2-por-cuadros-y-etapas.md), propuesto) tiene 2.304 registros en 192 cuadros, con 12 etapas por cuadro. Su hoja maestra (`RAG_2.xlsx`) la mantiene el equipo y **no se versiona**. Se convierte con:
```bash
python scripts/convert_rag_xlsx.py RAG_2.xlsx data/kb_v2   # en otra carpeta, para revisarla o probarla
python scripts/convert_rag_xlsx.py RAG_2.xlsx              # aquí: REEMPLAZA la base v1
```
El conversor valida la hoja completa y no escribe nada si encuentra errores. Reemplazar la base v1 exige reconstruir el índice y recalibrar `evidence_policy.json` (MIG-07 del [plan de migración](../../docs/00-gestion/plan-migracion-rag2.md)); antes, el equipo debe decidir su validación (P1: hoy Fuente, Validado por y Fecha validación están vacías) y si reemplaza la v1 (P7).

Desde MIG-06 el arranque compara el **hash del archivo** con el del índice: editar un texto obliga a reconstruir el índice aunque los ids no cambien.

## Modificar la base
1. Editar `entries.jsonl` (o reexportar desde la hoja cuando exista B-019).
2. Reconstruir el índice.
3. Ejecutar `pytest` y la sonda en vivo (`pytest -m live`).
4. Aplicar la matriz de impacto (`docs/README.md`): CHANGELOG, bitácora y esta nota de validación.
