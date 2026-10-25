# Estrategia de pruebas

*Última actualización: 2026-10-10*

| Nivel | Carpeta | Qué prueba | Cuándo corre |
|---|---|---|---|
| Unitarias | `tests/unit/` | Reglas del dominio (**cada signo de alarma**), casos de uso con dobles de los puertos | Cada cambio |
| Integración | `tests/integration/` | Adaptadores reales (BD, API FastAPI, healthcheck) | Cada PR |
| Conversacionales (golden) | `tests/conversational/` | Hoy: frases de referencia de las reglas de alarma (`alarm_phrases.json`): cada regla con ≥ 2 frases que la activan, frases que no deben activarla y frases cotidianas sin alarma. Futuro: conversaciones completas contra la consola | Cada PR y cada cambio de regla o prompt |

| En vivo | `tests/live/` (marcador `live`, excluidas por defecto y de la CI) | Contra Ollama real y el índice construido: sonda de recuperación (16 casos, meta ≥ 13 en top-3), **no contaminación** del análisis con preguntas educativas y detección del filtro 2 en reportes coloquiales | En el PC de pruebas: `pytest -m live -s` |

## Reglas
- Cada criterio de aceptación en Gherkin tiene al menos una prueba, registrada en la [trazabilidad](../01-especificacion/trazabilidad.md).
- Las reglas clínicas tienen pruebas positivas y negativas, incluidas variantes coloquiales del lenguaje.
- Las pruebas que usan el LLM real se marcan y se aíslan; las unitarias usan dobles deterministas.
- La cobertura es orientativa (los lineamientos no la hacen determinante); el dominio debe acercarse al 100 %.

## Evaluación de la base v2 (MIG-08)
`scripts/evaluate_kb_v2.py` tampoco es de aprobado/reprobado. Usa la columna Preguntas de la base v2 (mensajes reales etiquetados con su cuadro y su etapa) como banco de prueba:
- `alarmas` (sin Ollama): el filtro 1 sobre cada pregunta, contado por la ruta base del cuadro, con ejemplos de urgencias en cuadros de autocuidado. Es la medición previa a decidir la negación (P2) y la cobertura del catálogo (MIG-18).
- `recuperacion` (con Ollama): busca cada pregunta dejando fuera su propio registro y mide si el cuadro correcto queda primero o entre los tres primeros, la similitud de aciertos y fallos (para recalibrar `min_similarity`) y la etapa del primer resultado.
Sus funciones puras tienen pruebas unitarias (`tests/unit/test_evaluate_kb_v2.py`). Ver [instalación](../08-despliegue/instalacion.md).

## Comparación de modelos (B-022)
`scripts/benchmark_models.py` no es una prueba de aprobado/reprobado: mide combinaciones de modelos en el PC de pruebas (alcance, filtro 2, respaldo de las respuestas y tiempos) con los mismos casos de `tests/live/`: alcance, sonda y frases coloquiales que el filtro 1 no capta (`colloquial_alarm_phrases.json`, PROVISIONAL). Sus funciones puras tienen pruebas unitarias (`tests/unit/test_benchmark_models.py`). Ver [operacion.md](../08-despliegue/operacion.md).
