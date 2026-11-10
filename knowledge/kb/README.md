# Base de conocimiento (RAG)

`entries.jsonl` contiene **2.828 registros** pregunta/respuesta, uno por línea:
`{id, domain, category, focus, question, answer}`. *Indagar*: qué preguntar y qué señales importan · *Solucionar*: orientación.

| Dominio | Registros | Categorías | Indagar / Solucionar |
|---|---|---|---|
| `cardiovascular` | 1.413 | 8 originales (100–150 cada una) + 7 nuevas `CV-N1` a `CV-N7` (49–85 cada una) | 618 / 795 |
| `materno_infantil` | 1.415 | 8 originales (100–196 cada una) + 7 nuevas `MI-N1` a `MI-N7` (33–64 cada una) | 598 / 817 |

Las categorías `CV-N*` y `MI-N*` son las de la [matriz de cobertura](../../docs/04-datos/matriz-cobertura-base-conocimiento.md) (B-035).

## Origen y estado de validación
- **Origen:** generado con IA (ChatGPT Work) con trabajo intensivo por categoría y búsqueda de fuentes. Se mantenía en un Google Spreadsheet del equipo y se sincronizaba con `kb_sync` en el piloto anterior (`piloto-agente-nanomaterno-cardiovascular`). Se exportó el 2026-10-10 con `scripts/export_pilot_kb.py`, conservando el `id` (hash) del piloto.
- **Estado: `VALIDADA_PARA_PROTOTIPO`.** Decisión acordada con **Miguel, líder del proyecto** (TODO: apellido), el 2026-10-10: se usa en el prototipo como datos validados.
- **Ampliación del 2026-11-10 (B-035):** un compañero del equipo agregó a la hoja **1.228 registros** (828 en las 14 categorías nuevas de la matriz de cobertura y 400 en categorías originales); los 1.600 anteriores no cambiaron. **Estado: PENDIENTE DE VALIDACIÓN** hasta que el equipo decida D1–D7 de la matriz y el líder del proyecto los acepte para el prototipo. No traen fuente por registro.
- **Limitación:** los registros no tienen fuente, revisor ni fecha individuales. Para usar el asistente con usuarios reales se requiere la validación clínica (B-019: columnas Fuente/Validado por/Fecha en la hoja).

## Índice vectorial (derivado, no versionado)
El índice se genera desde este archivo y **no se sube a git** (`data/kb_index/`):
```bash
.venv/bin/python run_build_kb_index.py
```
Usa `OLLAMA_EMBED_MODEL` (por defecto `qwen3-embedding:8b`). Si este archivo o el modelo cambian, el asistente avisa al arrancar y hay que reconstruir el índice.

## Política de evidencia y verificación del respaldo
`knowledge/evidence_policy.json` define la búsqueda (umbral, `top_k`…; desde la v1.2.0, del 2026-10-12, el umbral es **0,50** por decisión del equipo) y, desde el ADR 0010, la verificación determinista de cada frase: `min_support` (0,6), `max_free_sentences` (2) y `max_free_words` (20). Desde la v1.6.0, `inquiry_max_questions_with_answer` (1) limita las preguntas que acompañan una respuesta (HU-13). Los umbrales también se pueden fijar en `.env` (`RAG_MIN_SIMILARITY`, `RAG_TOP_K`, `RAG_CANDIDATE_K`, `GROUNDING_*`), que tienen prioridad sobre el archivo. Cambiar estos valores no obliga a reconstruir el índice, pero sí a repetir `pytest -m live` (`test_live_grounding.py` mide cuántas respuestas terminan en texto literal).

**Efecto de la verificación:** una pregunta que la base no cubre (p. ej., qué comer con acidez o la dosis de insulina en la diabetes gestacional) recibe la abstención o el texto literal de un registro *Indagar*. Llenar esos vacíos es contenido clínico (B-019, B-035).

## Modificar la base
La hoja de Google del equipo es el origen. Para traer sus cambios:
1. Descargar cada pestaña (CARDIOVASCULAR y MATERNO-INFANTIL) con *Archivo → Descargar → Valores separados por comas (.csv)*.
2. Exportar: `python scripts/export_sheet_kb.py cardiovascular.csv materno_infantil.csv`. Calcula el `id` igual que `kb_sync`, así que los registros sin cambios conservan su id, y ordena como antes para que el diff muestre solo lo nuevo. Una fila editada en la hoja recibe un id nuevo.
3. Reconstruir el índice (`run_build_kb_index.py`, con Ollama: en el PC de pruebas o en MareNostrum 5). Recalcula todos los embeddings.
4. Ejecutar `pytest` y la sonda en vivo (`pytest -m live`).
5. Ajustar el conteo de `test_real_knowledge_base_and_policy_load` y aplicar la matriz de impacto (`docs/README.md`): CHANGELOG, bitácora y esta nota de validación.
