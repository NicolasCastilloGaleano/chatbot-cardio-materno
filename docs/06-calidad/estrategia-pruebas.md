# Estrategia de pruebas

*Última actualización: 2026-11-11*

| Nivel | Carpeta | Qué prueba | Cuándo corre |
|---|---|---|---|
| Unitarias | `tests/unit/` | Reglas del dominio (**cada signo de alarma**), casos de uso con dobles de los puertos | Cada cambio |
| Integración | `tests/integration/` | Adaptadores reales (BD, API FastAPI, healthcheck) | Cada PR |
| Conversacionales (golden) | `tests/conversational/` | Hoy: frases de referencia de las reglas de alarma (`alarm_phrases.json`): cada regla con ≥ 2 frases que la activan, frases que no deben activarla y frases cotidianas sin alarma. Futuro: conversaciones completas contra la consola | Cada PR y cada cambio de regla o prompt |

| En vivo | `tests/live/` (marcador `live`, excluidas por defecto y de la CI) | Contra Ollama real y el índice construido: sonda de recuperación (16 casos, meta ≥ 13 en top-3), **no contaminación** del análisis con preguntas educativas y detección del filtro 2 en reportes coloquiales; **sonda de cobertura** de las categorías nuevas (`coverage_probe.json`, 4 preguntas generales por categoría, meta ≥ 80 % en top-3; las categorías aún sin registros se informan y no cuentan) | En el PC de pruebas: `pytest -m live -s` |

## Reglas
- Cada criterio de aceptación en Gherkin tiene al menos una prueba, registrada en la [trazabilidad](../01-especificacion/trazabilidad.md).
- Las reglas clínicas tienen pruebas positivas y negativas, incluidas variantes coloquiales del lenguaje.
- Las pruebas que usan el LLM real se marcan y se aíslan; las unitarias usan dobles deterministas.
- La cobertura es orientativa (los lineamientos no la hacen determinante); el dominio debe acercarse al 100 %.

## Comparación de modelos (B-022)
**Medición antes y después de un cambio en la verificación (2026-10-26):** `tests/live/test_live_grounding.py` muestra cómo terminó cada respuesta (frases verificadas, texto literal, abstención o RAG no disponible). Antes de fusionar un cambio en `domain/grounding.py` o en `application/grounded_reply.py`, se ejecuta en `main` y en la rama, y se comparan los conteos de texto literal y de abstención. Desde B-028 (2026-10-27) también reporta las citas de cada respuesta y, en los literales, cuántas frases del registro se mostraron.

`scripts/benchmark_models.py` no es una prueba de aprobado/reprobado: mide combinaciones de modelos en el PC de pruebas (alcance, filtro 2, respaldo de las respuestas y tiempos) con los mismos casos de `tests/live/`: alcance, sonda y frases coloquiales que el filtro 1 no capta (`colloquial_alarm_phrases.json`, PROVISIONAL). Sus funciones puras tienen pruebas unitarias (`tests/unit/test_benchmark_models.py`). Ver [operacion.md](../08-despliegue/operacion.md).

## Comparación del prompt de análisis v8 y v9
El v9 (ADR 0023) agrega el campo `access_facts`. Las pruebas automáticas demuestran que el **código** no deja que ese campo cambie la alarma, el alcance, la búsqueda ni el hilo. **No demuestran** que el modelo, con un prompt más largo, siga respondiendo igual en los demás campos: eso solo se mide con Ollama.

**Requisitos (PC de pruebas):** Ollama en marcha, los modelos de `.env` (`OLLAMA_ANALYSIS_MODEL`, `OLLAMA_REPLY_MODEL`, `OLLAMA_EMBED_MODEL`), el índice construido (`python run_build_kb_index.py`) y `.venv` con `requirements-dev.txt`. No se cambia nada de `.env` entre una variante y la otra.

1. Batería en vivo con el v8 (línea base; es la misma de `main`):
   ```bash
   pytest -m live -s > en-vivo-v8.txt
   ```
2. La misma batería con el v9 (PowerShell):
   ```powershell
   $env:LIVE_ANALYSIS_PROMPT = "v9"; $env:CARE_ACCESS_MODE = "observar"; pytest -m live -s > en-vivo-v9.txt
   ```
3. Comparador (122 casos, tres repeticiones, con recuperación real):
   ```bash
   python scripts/compare_analysis_prompts.py --runs 3 --retrieval
   ```
   Una prueba rápida: `--limit 10 --runs 1`. Una sola batería: `--category "alarma + barrera"`.

**Cómo leer el informe** (`data/benchmarks/comparacion-v8-v9-*.md`):
- *Resultados contra lo esperado*, por batería: alarma detectada (con y sin el filtro 1), falsas alarmas, alcance, hilo, pregunta de información, datos de acceso y categoría recuperada.
- *Acuerdo v8~v9 frente al ruido*: el modelo no responde igual dos veces. El v9 solo se distingue del v8 en un campo si su acuerdo con el v8 es menor que el acuerdo del v8 consigo mismo.
- *Alarmas no detectadas* y casos discordantes: un caso que el v8 detecta y el v9 no es una regresión de seguridad, aunque la prueba de signos no sea significativa. Con este número de casos, no ver diferencia **no** demuestra equivalencia.
- *Ejecución*: errores, latencia p50 y p90 y el prompt más grande. Si `max_prompt_tokens` del v9 se acerca a `OLLAMA_ANALYSIS_NUM_CTX`, hay que subirlo para las dos variantes y repetir.

Los casos son sintéticos y no definen contenido clínico: la regla esperada de cada síntoma es la que ya le asignan las baterías existentes. Qué resultado basta para pasar de `apagado` a `observar` lo decide el equipo (pendiente 21).

