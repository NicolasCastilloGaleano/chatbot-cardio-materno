# Borradores de la ronda 2 de la base (B-036)

*Última actualización: 2026-11-12*

> **Estado: INTEGRADA en `knowledge/kb/entries.jsonl` (2026-11-12)**, tras la revisión del equipo según el usuario. Redactada con IA (Claude Code). Los registros se agregaron directamente a la base, sin pasar por la hoja: **hay que pegarlos en la hoja de Google antes de la próxima exportación**, o se perderán. Especificación: [matriz de cobertura §11](../../matriz-cobertura-base-conocimiento.md). Fuentes: [catálogo](../../fuentes-base-conocimiento.md).

## Qué hay
**1.221 registros en 30 archivos** (2026-11-12): 498 de determinantes sociales (`CV-S*`, `MI-S*`), 399 de temas faltantes (`CV-T*`, `MI-T*`) y 324 para completar 13 categorías de la ronda 1. Con ellos, la base pasaría de 2.828 a unos **4.049 registros**. `scripts/check_kb.py` sobre todos juntos: 0 errores y 0 avisos. Las dudas de cada lote (afirmaciones sin fuente directa, fuentes que faltan, decisiones clínicas) están en [dudas-revision.md](dudas-revision.md).

Un CSV por categoría (`<código>.csv`) con las columnas `Categoría, Enfoque, Preguntas, Respuestas, Fuente, Tipo`:
- `CV-S*` y `MI-S*`: determinantes sociales de la salud.
- `CV-T*` y `MI-T*`: temas que faltaban.
- `CV-N*` y `MI-N*`: registros para completar las categorías cortas de la ronda 1.

*Fuente* cita los `id` del catálogo. *Tipo* distingue las preguntas `general` (básicas) de las de `escenario`.

## Cómo revisar
1. Revisar con `python scripts/check_kb.py docs/04-datos/borradores-kb/ronda-2/*.csv`: debe terminar con **Errores: 0**.
2. Leer los registros. **Revisión del 100 %** en:
   - MI-S3 (violencias y protección);
   - MI-T2 (infecciones en el embarazo);
   - CV-N4 y MI-N4 (primeros auxilios).

   En el resto, al menos el 20 % de cada categoría, elegido al azar.
3. Para los registros de determinantes sociales, conviene la mirada de trabajo social o salud pública: que no estigmaticen y que las rutas sean correctas para Caldas.
4. Qué rechazar o corregir:
   - una frase sin respaldo en la fuente citada;
   - un dato local inventado;
   - una dosis o un diagnóstico;
   - un tono que juzgue a la persona;
   - una orientación de urgencia que contradiga los avisos del asistente.
5. Anotar las decisiones en la columna *Fuente* o en una columna aparte de la hoja ("Validado por", "Fecha"), como pide B-019.

## Cómo pasarlos a la base
1. Pegar las filas aprobadas al final de la pestaña que corresponda: **CARDIOVASCULAR** para `CV-*` y **MATERNO-INFANTIL** para `MI-*`. Las columnas *Fuente* y *Tipo* pueden ir en la hoja, porque la exportación las ignora.
2. Descargar las dos pestañas en CSV y exportar:
   ```bash
   python scripts/export_sheet_kb.py cardiovascular.csv materno_infantil.csv
   ```
3. Revisar la base completa con `python scripts/check_kb.py knowledge/kb/entries.jsonl`, actualizar el conteo de `tests/unit/test_rag_components.py` y correr `pytest`.
4. En MareNostrum 5: `bash scripts/mn5/pedir_gpu.sh indice live`, con `OLLAMA_REPLY_MODEL=qwen3:8b`. Ahí se ve la nueva sonda de cobertura (`tests/live/test_live_coverage.py`).
