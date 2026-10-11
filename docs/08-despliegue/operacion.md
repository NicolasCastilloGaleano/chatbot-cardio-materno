# Operación y mantenimiento

*Última actualización: 2026-10-10*

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

**Registra los resultados** (configuración y tiempos) en la bitácora, para decidir los valores por defecto con datos.

## Pendiente
TODO al desplegar: healthcheck, logs, rotación de secretos, actualización de la base de conocimiento y de las reglas clínicas, y respaldo de datos.
