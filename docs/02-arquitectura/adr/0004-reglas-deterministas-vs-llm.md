# ADR 0004: Reglas clínicas deterministas; el LLM solo interpreta y redacta

- **Estado:** Aceptado
- **Fecha:** 2026-10-09
- **Decisores:** equipo de desarrollo (pendiente de ratificación por el equipo clínico)

## Contexto
Los LLM pueden alucinar, varían entre ejecuciones y no son auditables. En teleorientación materno‑infantil y cardiovascular, un signo de alarma no detectado puede costar una vida.

## Decisión
- La **detección de signos de alarma**, la **clasificación de urgencia** y la **ruta de atención** son reglas **deterministas** en `domain/`, definidas y validadas por el equipo clínico y con pruebas por cada regla.
- El LLM se usa solo para: (a) interpretar el texto libre y extraer intención y síntomas en un formato estructurado, y (b) redactar respuestas de orientación a partir de contenido validado (RAG), con guardrails.
- Como red de seguridad, además del LLM se aplica una detección por palabras clave o patrones. Si cualquiera de las dos detecta una alarma, prevalece la alarma.
- Los mensajes de urgencia son **plantillas fijas** que no genera el LLM.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Que el LLM decida todo | Menos código | No auditable ni reproducible; riesgo clínico inaceptable |
| Solo reglas y menús, sin LLM | Totalmente determinista | Experiencia rígida; no cumple la actividad 2.2 |

## Consecuencias
- ✅ La seguridad es auditable y testeable, cumple el principio de "no diagnóstico" y facilita el informe de gobernanza.
- ⚠️ Requiere que el equipo clínico mantenga el catálogo de reglas.
