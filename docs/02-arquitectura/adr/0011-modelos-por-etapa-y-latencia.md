# ADR 0011: Modelos por etapa y estrategia de latencia

- **Estado:** Propuesto. **Falta la decisión del equipo** con los datos de `scripts/benchmark_models.py`
- **Fecha:** 2026-10-11
- **Decisores:** equipo del proyecto (pendiente). Elegir el modelo no se delega a la IA (AGENTS.md §5)
- **Relacionado:** ADR 0005 (Ollama local), ADR 0008 (dos llamadas), ADR 0010 (respuesta verificada), B-022

## Contexto
En el guion del 2026-10-11, cada turno tardó entre 30 y 75 s:

| Etapa | Tiempo |
|---|---|
| Análisis | 13–28 s |
| RAG | 7 s con el embedder en automático; 0,5–0,8 s con el embedder en CPU |
| Respuesta | 15–42 s |

`mistral-small3.1:24b` ocupa unos 15 GB y no cabe en la RTX 2080 SUPER de 8 GB, así que Ollama lo reparte entre la GPU y la CPU. Generar con la parte en CPU cuesta tiempo por cada token. Hasta un "hola" tarda 27 s.

## Medidas ya implementadas (no requieren decisión)
1. **Embedder en CPU por defecto** (`OLLAMA_EMBED_NUM_GPU=0`; `auto` deja decidir a Ollama). Bajó el RAG de 7 s a menos de 1 s.
2. **Abstención sin LLM** (ADR 0010): sin evidencia suficiente, el turno no hace la llamada de respuesta.
3. **Respuesta más corta:** máximo ~90 palabras en el prompt de respuesta v3.
4. **Límite de tokens por etapa** (`OLLAMA_ANALYSIS_NUM_PREDICT`=600 y `OLLAMA_REPLY_NUM_PREDICT`=500, holgados) para cortar respuestas desbocadas.
5. **Precalentamiento al arrancar:** se cargan los modelos de análisis, de respuesta y de embeddings antes del primer turno.
6. `OLLAMA_THINK` opcional, para desactivar el razonamiento de modelos como qwen3 si el equipo los elige.

## Decisión pendiente: qué modelo usa cada etapa
Opciones que caben en 8 GB con `num_ctx` 4096:

| Opción | Análisis | Respuesta | Esperado |
|---|---|---|---|
| A (actual) | mistral-small3.1:24b | mistral-small3.1:24b | Calidad conocida; 30–75 s por turno |
| B | qwen3:8b o llama3.1:8b | mistral-small3.1:24b | Análisis mucho más rápido; respuesta igual |
| C | qwen3:8b o llama3.1:8b | qwen3:8b o llama3.1:8b | Todo en GPU; lo más rápido |
| D | mistral-nemo:12b | mistral-nemo:12b | Punto intermedio |

**Cómo decidir:** ejecutar en el PC de pruebas, después de descargar los candidatos con `ollama pull`:

```bash
.venv/bin/python scripts/benchmark_models.py mistral-small3.1:24b qwen3:8b+mistral-small3.1:24b qwen3:8b llama3.1:8b mistral-nemo:12b
```

### Ronda 1 (2026-10-12, PC de pruebas)
| Análisis | Respuesta | Errores JSON | Alcance | Filtro 2 | Verificadas | Literal | Abstención | Otros | Turno p50 | Turno p90 | Análisis p50 | Respuesta p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistral-small3.1:24b | mistral-small3.1:24b | 0 | 9/9 | 18/20 | 9 | 0 | 0 | 7 | 47.1 s | 60.6 s | 19.0 s | 34.5 s |
| qwen3:8b | mistral-small3.1:24b | 1 | 8/9 | 17/20 | 7 | 0 | 1 | 8 | 18.7 s | 70.0 s | 5.5 s | 48.1 s |
| qwen3:8b | qwen3:8b | 3 | 8/9 | 16/20 | 6 | 1 | 0 | 9 | 9.8 s | 16.4 s | 6.1 s | 5.9 s |
| llama3.1:8b | llama3.1:8b | 0 | 8/9 | 12/20 | 2 | 5 | 0 | 9 | 2.9 s | 9.0 s | 1.2 s | 2.4 s |
| mistral-nemo:12b | mistral-nemo:12b | 0 | 9/9 | 16/20 | 4 | 4 | 0 | 8 | 12.3 s | 25.0 s | 5.4 s | 8.4 s |

**Lectura:**
- **Se descartan dos combinaciones.** La mixta qwen3 + mistral, porque los dos modelos se intercambian en los 8 GB de VRAM y la respuesta se vuelve más lenta (p90 de 70 s). Y llama3.1, porque el filtro 2 bajó a 12/20 y 5 de 7 respuestas terminaron en texto literal.
- **La columna "Filtro 2" no servía para comparar.** El filtro 1 capta las 20 frases que se usaron, así que ninguna falla se habría perdido en producción. Las fallas comunes a todos los modelos (RN-MI-09, RN-MI-12, RN-MI-14) vienen de patrones del catálogo que solo aceptan el nombre exacto del signo. Esas preguntas se enviaron al equipo clínico.
- **Los modelos pequeños copiaron los marcadores del prompt v3.** Por ejemplo, "[lo que describió la persona]" o "desde hace [N] días", lo que además inventa el dato. Se corrigió con el prompt v4 y con una protección determinista: los síntomas con marcadores quedan marcados y se quitan del resumen y de la consulta.
- **Los errores de JSON de qwen3** probablemente vienen de su razonamiento, que agota el límite de tokens. Se repite con `OLLAMA_THINK=false`.

### Ronda 2 (pendiente)
Mide el filtro 2 con frases coloquiales que el filtro 1 **no** capta (`tests/live/colloquial_alarm_phrases.json`), imprime las frases descartadas y precalienta los modelos con las mismas opciones que las consultas. Candidatos: `mistral-small3.1:24b` (referencia), `mistral-nemo:12b` y `qwen3:8b` sin razonamiento.

**Criterios propuestos** (los confirma el equipo):
1. **Filtro 2 sin pérdida:** en las frases coloquiales que el filtro 1 no capta, las reglas detectadas no bajan frente a la opción A. Es seguridad clínica: no se negocia.
2. **Alcance:** acierta los 9 casos compartidos.
3. **JSON:** 0 errores.
4. **Respuestas:** la proporción de texto literal no sube mucho frente a la opción A (si el modelo no parafrasea de cerca, el verificador lo reemplaza).
5. **Latencia:** turno p50 ≤ 15 s.

## Consecuencias
- Cuando el equipo decida, este ADR pasa a **Aceptado** con la tabla del informe (`data/benchmarks/`), se ajustan `OLLAMA_ANALYSIS_MODEL` / `OLLAMA_REPLY_MODEL` en `.env.example` y se repite `pytest -m live`.
- ⚠️ Un modelo más pequeño puede reportar peor los síntomas. Por eso el criterio 1 es obligatorio y las reglas del filtro 1 siguen revisando el texto original.
