# Estrategia de pruebas

*Última actualización: 2026-10-10*

| Nivel | Carpeta | Qué prueba | Cuándo corre |
|---|---|---|---|
| Unitarias | `tests/unit/` | Reglas del dominio (**cada signo de alarma**), casos de uso con dobles de los puertos | Cada cambio |
| Integración | `tests/integration/` | Adaptadores reales (BD, API FastAPI, healthcheck) | Cada PR |
| Conversacionales (golden) | `tests/conversational/` | Hoy: frases de referencia de las reglas de alarma (`alarm_phrases.json`): cada regla con ≥ 2 frases que la activan, frases que no deben activarla y frases cotidianas sin alarma. Futuro: conversaciones completas contra la consola | Cada PR y cada cambio de regla o prompt |

## Reglas
- Cada criterio de aceptación en Gherkin tiene al menos una prueba, registrada en la [trazabilidad](../01-especificacion/trazabilidad.md).
- Las reglas clínicas tienen pruebas positivas y negativas, incluidas variantes coloquiales del lenguaje.
- Las pruebas que usan el LLM real se marcan y se aíslan; las unitarias usan dobles deterministas.
- La cobertura es orientativa (los lineamientos no la hacen determinante); el dominio debe acercarse al 100 %.
