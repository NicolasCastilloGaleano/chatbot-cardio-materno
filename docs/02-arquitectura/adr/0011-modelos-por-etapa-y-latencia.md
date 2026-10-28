# ADR 0011: Modelos por etapa y estrategia de latencia

- **Estado:** **Aceptado** por el equipo el 2026-10-12: análisis `mistral-small3.1:24b`, respuesta `qwen3:8b` sin razonamiento y umbral del RAG 0,50. Combinación medida (ver "Medición de la combinación elegida"). Se revisará si cambia el hardware o aparece un modelo de análisis más rápido con el mismo filtro 2
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

### Ronda 2 (2026-10-12): 18 frases coloquiales que el filtro 1 no captaba (catálogo v0.3.1)
| Análisis | Respuesta | Errores JSON | Alcance | Filtro 2 (coloquiales) | Verificadas | Literal | Abstención | Otros | Turno p50 | Turno p90 | Análisis p50 | Respuesta p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistral-small3.1:24b | mistral-small3.1:24b | 0 | 9/9 | 14/18 | 7 | 2 | 0 | 7 | 47.5 s | 55.9 s | 19.8 s | 35.5 s |
| mistral-nemo:12b | mistral-nemo:12b | 0 | 9/9 | 12/18 | 6 | 2 | 0 | 8 | 10.7 s | 13.7 s | 5.9 s | 8.1 s |
| qwen3:8b (sin razonar) | qwen3:8b (sin razonar) | 0 | 8/9 | 9/18 | 8 | 0 | 0 | 8 | 3.4 s | 5.3 s | 1.7 s | 2.6 s |

**Lectura:**
- **qwen3 no sirve para el análisis.** Sin razonar ya no tiene errores de JSON y redacta muy bien (8 verificadas, 0 literal), pero omite síntomas: dejó vacío "se cayó redondo y no respondía" y copia las palabras sin traducirlas.
- **Parte de las fallas del filtro 2 eran de los patrones, no de los modelos.** Por ejemplo, "Vómito de todo lo que come o bebe" no activaba "Vomita todo…". Se ampliaron los patrones (catálogo v0.4.0, pendiente de aprobación clínica), con lo que el filtro 1 pasa a captar 7 de las 18 frases. Y se propone la solución de fondo, los códigos cerrados ([ADR 0012](0012-signos-reportados-como-codigos-cerrados.md)).
- **Las frases descartadas eran de verdad agregados sin respaldo**, como "el dolor puede extenderse al brazo…" o "sigue una dieta saludable". El verificador acertó.

### Ronda 3 (2026-10-12): con los códigos cerrados (ADR 0012) y el catálogo v0.5.0
| Análisis | Respuesta | Errores JSON | Alcance | Filtro 2 (coloquiales) | Filtro 2 por código | Verificadas | Literal | Abstención | Otros | Turno p50 | Turno p90 | Análisis p50 | Respuesta p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistral-small3.1:24b | mistral-small3.1:24b | 0 | 9/9 | 16/18 | 16/18 | 8 | 0 | 0 | 8 | 49.9 s | 64.9 s | 25.5 s | 36.4 s |
| llama3.1:8b | llama3.1:8b | 0 | 5/9 | 14/18 | 7/18 | 5 | 2 | 0 | 9 | 2.1 s | 4.5 s | 1.6 s | 2.4 s |
| mistral-nemo:12b | mistral-nemo:12b | 0 | 8/9 | 15/18 | 15/18 | 3 | 2 | 0 | 11 | 7.5 s | 21.1 s | 7.3 s | 9.6 s |
| qwen3:8b | qwen3:8b | 0 | 8/9 | 15/18 | 13/18 | 5 | 1 | 0 | 10 | 2.4 s | 5.2 s | 2.1 s | 2.8 s |
| qwen3:8b | mistral-small3.1:24b | 0 | 8/9 | 15/18 | 14/18 | 5 | 1 | 0 | 10 | 9.5 s | 66.5 s | 2.1 s | 46.6 s |

**Lectura (comparada con la ronda 2):**
- **Los códigos cerrados mejoran a todos los modelos.** En el filtro 2: mistral-small pasa de 14 a 16 de 18, nemo de 12 a 15 y qwen3 de 9 a 15. En mistral-small y nemo casi todos los aciertos llegan por código.
- **Errores de interpretación que siguen apareciendo:**
  - qwen3 y nemo marcaron `SIGNOS_ACV` en convulsiones ("ojos en blanco y temblaba", "ataque y se puso rígida");
  - nemo marcó `SANGRADO_VAGINAL_EMBARAZO_POSPARTO` para "me orino sola" (falso positivo);
  - qwen3 no reconoció "se cayó redondo y no respondía" (desmayo).

  Ningún modelo reconoce "me orino sola" (RN-MI-05) como salida de líquido: puede que la frase de prueba esté mal asignada (pregunta 4 al equipo clínico).
- **llama3.1 se descarta:** alcance 5/9 (no descarta los mensajes ajenos).
- **qwen3 es excelente redactando:** 5 verificadas y 1 literal con 2,8 s, frente a los 36 s de mistral-small.
- **Las combinaciones mixtas sufren el intercambio de modelos en la VRAM:** con qwen3 en el análisis y mistral en la respuesta, la respuesta tarda 46,6 s y el turno p90 sube a 66,5 s.

### Decisión (2026-10-12, equipo)
- **Análisis:** `mistral-small3.1:24b`, el mejor filtro 2 (16/18) y alcance 9/9.
- **Respuesta:** `qwen3:8b` con `OLLAMA_REPLY_THINK=false`: redacción verificada y muy rápida.
- **Umbral del RAG:** de 0,55 a 0,50 (algunos registros útiles quedaban justo por debajo). Política de evidencia v1.2.0; se puede ajustar con `RAG_MIN_SIMILARITY` en `.env`.

**Riesgo de la decisión:** esta combinación exacta **no se midió**. La inversa (qwen3 en el análisis + mistral en la respuesta) mostró el costo de intercambiar dos modelos que no caben juntos en 8 GB de VRAM. Hay que medirla antes de darla por definitiva:
```bash
OLLAMA_REPLY_THINK=false .venv/bin/python scripts/benchmark_models.py mistral-small3.1:24b+qwen3:8b
```
### Medición de la combinación elegida (2026-10-12)
| Análisis | Respuesta | Errores JSON | Alcance | Filtro 2 (coloquiales) | Filtro 2 por código | Verificadas | Literal | Abstención | Otros | Turno p50 | Turno p90 | Análisis p50 | Respuesta p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mistral-small3.1:24b | qwen3:8b | 0 | 9/9 | 16/18 | 16/18 | 6 | 1 | 1 | 8 | 46.5 s | 61.1 s | 26.0 s | 9.5 s |

- **Calidad:** la mejor de las medidas (alcance 9/9 y filtro 2 16/18, todo por código; sin errores de JSON).
- **Latencia:** turno p50 46,5 s, frente a 49,9 s con mistral-small en las dos etapas. La respuesta baja de 36 s a 9,5 s (qwen3 solo tarda 2,8 s; la diferencia es el intercambio de modelos en la VRAM), pero el análisis con 24B (26 s) sigue siendo el cuello de botella.
- **Se acepta** priorizando la seguridad del filtro 2 sobre la latencia. **La meta de 15 s por turno no se cumple**: queda para trabajo futuro (un modelo de análisis más rápido con el mismo filtro 2, o una GPU con más memoria).

Alternativas que se descartaron con estos datos:
- `qwen3:8b` en las dos etapas, la más rápida, con un filtro 2 de 15/18;
- `mistral-small3.1:24b` en las dos, la más segura (unos 50 s por turno).

**Criterios propuestos** (los confirma el equipo):
1. **Filtro 2 sin pérdida:** en las 18 frases coloquiales (`colloquial_alarm_phrases.json`), las reglas que detecta el filtro 2 por sí solo no bajan frente a la opción A. Es seguridad clínica: no se negocia.
2. **Alcance:** acierta los 9 casos compartidos.
3. **JSON:** 0 errores.
4. **Respuestas:** la proporción de texto literal no sube mucho frente a la opción A (si el modelo no parafrasea de cerca, el verificador lo reemplaza).
5. **Latencia:** turno p50 ≤ 15 s.

## Consecuencias
- La decisión quedó en `.env.example` (`OLLAMA_ANALYSIS_MODEL`, `OLLAMA_REPLY_MODEL`, `OLLAMA_REPLY_THINK=false`). Todos los parámetros de cada etapa (modelo, temperatura, contexto, tiempo de espera, razonamiento y límite de tokens) se configuran en `.env`. Falta repetir `pytest -m live` con la combinación elegida.
- ⚠️ Un modelo más pequeño puede reportar peor los síntomas. Por eso el criterio 1 es obligatorio y las reglas del filtro 1 siguen revisando el texto original.

## Actualización 2026-10-27: contexto del análisis en 8192
En el guion de la HU-11, la llamada de análisis llenó el contexto de 4096 tokens (`n_tokens = 4095, truncated = 1` en el log de Ollama) y el JSON llegó cortado: la web respondió 502. Con el v6 las llamadas ya rondaban 3900-4000 tokens (catálogo de signos con ejemplos, hilo y JSON); el prompt v7 las pasó del límite en los hilos largos. Se decide:
- el análisis usa un contexto de **8192** si `OLLAMA_ANALYSIS_NUM_CTX` está vacía (antes heredaba `OLLAMA_NUM_CTX` = 4096); la respuesta sigue en 4096;
- cuando Ollama corta por límite (`done_reason` "length"), el error lo dice ("límite de contexto o de tokens") y el log de la web y de WhatsApp registra la etapa.

Pendiente: medir en el PC el tiempo del análisis con 8192 (más memoria para el caché del modelo de 24B, que no cabe entero en la GPU) frente a los 13-28 s medidos con 4096.

