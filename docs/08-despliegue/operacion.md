# Operación y mantenimiento

*Última actualización: 2026-10-11*

## Diagnóstico de latencia (PC de pruebas)
Cada turno en alcance hace hasta **tres solicitudes a Ollama**: análisis (LLM), embedding de la consulta (RAG) y respuesta (LLM). La línea `[tiempos …]` muestra cuánto tarda cada una.

**Medición del 2026-10-10** (RTX 2080 SUPER de 8 GB, 128 GB de RAM): análisis 13–23 s, RAG 7,2 s constante y respuesta 28–38 s, unos 60 s por turno.

**Hipótesis:** `mistral-small3.1:24b` y `qwen3-embedding:8b` no caben juntos en 8 GB de VRAM y Ollama **descarga y recarga** los modelos en cada turno. El RAG constante de 7,2 s apunta a la carga del embedder.

### Pasos
1. **Ver qué está cargado.** Mientras el chat responde, en otra terminal:
   ```bash
   watch -n 1 ollama ps
   ```
   La columna `PROCESSOR` muestra cuánto de cada modelo está en GPU y cuánto en CPU. Si los modelos aparecen y desaparecen entre etapas, hay intercambio.
2. **Embedder en CPU.** Así deja la GPU al LLM; con 64 hilos, el embedding de una consulta corta debería ser rápido. En `.env`:
   ```
   OLLAMA_EMBED_NUM_GPU=0
   ```
   Reinicia `run_console.py` y compara los `[tiempos …]`.
3. **Mantener los modelos cargados entre turnos.** `OLLAMA_KEEP_ALIVE=30m` ya viene por defecto en `.env.example`; sube el valor si hace falta.
4. **Opcional, en el servidor de Ollama:** permitir dos modelos cargados a la vez (`sudo systemctl edit ollama`):
   ```
   [Service]
   Environment="OLLAMA_MAX_LOADED_MODELS=2"
   ```
   Luego: `sudo systemctl restart ollama`.
5. **Sin código:** probar un modelo más pequeño solo para el análisis (`OLLAMA_ANALYSIS_MODEL`), manteniendo `mistral-small3.1:24b` en la respuesta. Hay que verificar después con `pytest -m live` que el filtro 2 y el alcance siguen funcionando.

**Medición del 2026-10-11** (guion manual): con el embedder en CPU, el RAG bajó de 7,2 s a 0,5–0,8 s. El análisis (13–28 s) y la respuesta (15–42 s) siguen siendo el cuello de botella, porque el modelo de 24B no cabe en la GPU.

**Ya aplicado (ADR 0011):** embedder en CPU por defecto, precalentamiento de los modelos al arrancar, límite de tokens por etapa, respuesta de ~90 palabras y abstención sin llamar al LLM.

## Comparación de modelos (B-022, ADR 0011)
Para decidir qué modelo usa cada etapa:

1. Descarga los candidatos: `ollama pull qwen3:8b`, `ollama pull llama3.1:8b`, `ollama pull mistral-nemo:12b`.
2. Ejecuta la comparación (cada combinación tarda entre 5 y 25 minutos según el modelo). Cada argumento es `MODELO` (ambas etapas) o `ANÁLISIS+RESPUESTA`. **Ronda 3**, con los códigos cerrados (ADR 0012) y todas las combinaciones de la ronda 1. qwen3 va aparte, con su razonamiento desactivado **solo en la etapa donde se usa** (`OLLAMA_ANALYSIS_THINK` / `OLLAMA_REPLY_THINK`):
   ```bash
   .venv/bin/python scripts/benchmark_models.py mistral-small3.1:24b llama3.1:8b mistral-nemo:12b
   ```
   ```bash
   OLLAMA_ANALYSIS_THINK=false OLLAMA_REPLY_THINK=false .venv/bin/python scripts/benchmark_models.py qwen3:8b
   ```
   ```bash
   OLLAMA_ANALYSIS_THINK=false .venv/bin/python scripts/benchmark_models.py qwen3:8b+mistral-small3.1:24b
   ```
3. El informe se imprime y queda en `data/benchmarks/` (no se versiona). Columnas:
   - errores de JSON;
   - aciertos de alcance (9 casos);
   - reglas que detecta el filtro 2 por sí solo en 18 frases coloquiales (`tests/live/colloquial_alarm_phrases.json`), por texto o por código; la columna "Filtro 2 por código" cuenta las de la vía de códigos, y la consola dice la vía de cada acierto y marca las que también capta el filtro 1;
   - turnos verificados, con texto literal, con abstención u otros (16 consultas de la sonda);
   - tiempos p50/p90 del turno, del análisis y de la respuesta.

   En la salida de la consola, cada turno con texto literal lista sus frases descartadas: sirven para calibrar `min_support`.
4. Lleva el informe al equipo: la decisión se registra en el ADR 0011 con los criterios que allí se proponen. **El filtro 2 no puede perder detecciones.**

## Pendiente
TODO al desplegar: healthcheck, logs, rotación de secretos, actualización de la base de conocimiento y de las reglas clínicas, y respaldo de datos.
