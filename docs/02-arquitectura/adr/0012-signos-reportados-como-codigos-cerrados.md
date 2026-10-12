# ADR 0012: Signos reportados como códigos cerrados del catálogo (B-015)

- **Estado:** Propuesto. **Falta la decisión del equipo**, porque cambia cómo funciona el filtro 2 de seguridad (AGENTS.md §5)
- **Fecha:** 2026-10-12
- **Propone:** Claude Code (Opus 5.5), a pedido de Nicolas Castillo Galeano
- **Relacionado:** ADR 0004 (reglas deterministas), ADR 0007 (doble filtro), ADR 0011 (modelos y latencia), B-015, riesgo R-09

## Contexto
Hoy el análisis escribe `reported_symptoms` en **texto libre**. El filtro 2 revisa ese texto con las mismas expresiones regulares del filtro 1 o con el nombre exacto del signo (la versión puente del ADR 0007). Esto falla cada vez que el modelo describe bien el síntoma, pero con otras palabras:

| Fecha | Descripción del modelo | Regla que no se activó | Diferencia |
|---|---|---|---|
| 2026-10-10 | "secreción vaginal rosada" | RN-MI-01 | Otra forma de nombrar el sangrado |
| 2026-10-10 | "disminución de los movimientos del bebé" | RN-MI-06 | "del bebé" en lugar de "fetales" |
| 2026-10-12 | "**Vómito** de todo lo que come o bebe" | RN-MI-10 ("**Vomita** todo…") | Una sola palabra |
| 2026-10-12 | "Fiebre en bebé de 10 días" | RN-MI-13 | Falta el texto "recién nacido" |
| 2026-10-12 | "Parálisis repentina en la mitad del cuerpo" | RN-CV-03 | Sinónimo |

Cada vez se amplían los patrones (catálogo v0.2.0, v0.3.0, v0.3.1 y v0.4.0), pero el problema de fondo sigue ahí: **la seguridad depende de la redacción del modelo**. Además, eso distorsiona la comparación de modelos del ADR 0011, que termina midiendo qué modelo acierta el vocabulario de los patrones y no qué modelo entiende mejor a la persona.

## Propuesta
1. **Código estable por signo** en `knowledge/alarm_rules.json` (campo `code`, p. ej. `VOMITO_TODO`, `FIEBRE_RECIEN_NACIDO`, `ACV_SIGNOS`). Va separado del nombre legible (`sign`), así cambiar la redacción del nombre no cambia el contrato. La población forma parte del código: `FIEBRE_EMBARAZO_POSPARTO` y `FIEBRE_RECIEN_NACIDO` son códigos distintos.
2. **Campo nuevo en el análisis:** `reported_signs`, una lista restringida por `enum` a los códigos del catálogo en el JSON Schema. Ollama obliga a que la salida sea uno de esos valores, así que no puede inventar códigos.
3. **Se conserva `reported_symptoms` en texto libre**, para auditar y para el filtro 2 actual. Las dos vías **solo suman**: una regla se activa si su código aparece en `reported_signs` **o** si sus patrones o su nombre coinciden con el texto. Nunca se pierde una detección que hoy existe.
4. **Cruce exacto y determinista:** código → regla(s) → severidad y mensaje fijo, en `domain/`. El modelo solo traduce el lenguaje de la persona a un signo de la lista cerrada. La severidad, el mensaje y la ruta los sigue decidiendo la regla, como exige el ADR 0004.
5. **Prompt de análisis:** la lista de signos (`{{SIGNOS_DE_ALARMA}}`) pasa a ser una tabla código → descripción → ejemplos coloquiales, y una instrucción: "marca un código solo si la persona describe ese signo; ante la duda entre dos, marca los dos". Las alarmas falsas por exceso se aceptan (criterio conservador del ADR 0007) y quedan en la traza.
6. **Traza y alertas:** cada alerta registra si vino del filtro 1, del texto del filtro 2 o del código del filtro 2. Así se mide cuánto aporta cada vía.
7. **Verificación:**
   - pruebas unitarias del cruce;
   - las frases de `tests/conversational/alarm_phrases.json` siguen pasando;
   - en vivo, `tests/live/colloquial_alarm_phrases.json` con cada modelo candidato (ronda 3 del ADR 0011).

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Seguir ampliando patrones (estado actual) | Sin cambios de arquitectura | Nunca termina: cada modelo y cada persona describe distinto; la comparación de modelos queda sesgada |
| Similitud por embeddings entre el síntoma y el nombre del signo | Tolera sinónimos | El umbral no es interpretable; no es determinista ni auditable de forma simple |
| El LLM devuelve directamente la severidad | Simple | **Viola el ADR 0004:** el LLM decidiría la alarma |
| **Códigos cerrados + texto libre en paralelo (propuesta)** | Cruce exacto, auditable; el modelo no puede inventar códigos; no pierde nada de lo actual | Prompt más largo (más tiempo de análisis); la tabla de códigos es contenido clínico y debe validarse |

## Consecuencias
- ✅ El filtro 2 deja de depender de la redacción: si el modelo entiende el síntoma, lo traduce a un código válido.
- ✅ La comparación de modelos mide comprensión y no vocabulario. Un modelo más rápido (p. ej., mistral-nemo, unos 11 s por turno frente a 47 s) podría cumplir el criterio de seguridad del ADR 0011.
- ⚠️ **Contenido clínico:** los códigos, sus descripciones y sus ejemplos coloquiales los valida el equipo clínico, igual que el catálogo actual (PROVISIONAL hasta entonces).
- ⚠️ El modelo puede marcar un código de más: es un falso positivo, aceptado por criterio conservador y visible en la traza.
- ⚠️ El prompt crece: hay que medir el tiempo del análisis en la ronda 3.

## Decisiones que pide al equipo
1. ¿Se aprueba el enfoque (códigos cerrados en paralelo con el texto libre)?
2. ¿Quién valida la tabla de códigos, descripciones y ejemplos coloquiales?
3. ¿Se implementa antes de elegir el modelo (ADR 0011)? Es lo que recomienda este ADR, para que la comparación sea justa.
