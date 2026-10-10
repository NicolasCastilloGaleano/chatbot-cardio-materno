# ADR 0007: Alarmas deterministas con doble filtro y catálogo como datos

- **Estado:** Aceptado
- **Fecha:** 2026-10-10
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano). Las reglas clínicas concretas quedan **PROVISIONALES** hasta la validación del equipo clínico (AGENTS.md §5).
- **Relacionado:** ADR 0004 (reglas deterministas vs. LLM), ADR 0006 (hilos).

## Contexto
Desde la HU-00 el prototipo conversaba libremente con el LLM sin detección de alarmas (riesgo R-07), lo que contradecía temporalmente el ADR 0004. La actividad 2.4 del proyecto exige alertas y rutas de atención oportunas. Los usuarios describen síntomas con palabras coloquiales ("me sale agüita con sangre por abajo") que unas reglas simples pueden no captar, mientras que el agente suele reformularlas en términos estándar.

## Decisión
1. **Catálogo como datos:** las reglas viven en `knowledge/alarm_rules.json`. Cada regla tiene ID trazable (`RN-MI-xx`, `RN-CV-xx`), dominio, población, signo, severidad, patrones (regex sobre texto normalizado), mensaje fijo y fuente. El equipo clínico lo revisa sin leer código. Si el catálogo es inválido, el programa no arranca.
2. **Dos severidades:**
   - `urgencia_inmediata`: solo se muestra el mensaje fijo (acudir a urgencias o llamar al 123), sin respuesta del LLM;
   - `consulta_prioritaria`: el mensaje fijo seguido de la respuesta del agente.
3. **Doble filtro determinista** (propuesta del usuario):
   - **Filtro 1:** antes del LLM, sobre el **texto original** del usuario. Si hay urgencia inmediata, **no se consulta al LLM**.
   - **Filtro 2:** después del LLM, sobre el campo `reported_symptoms`. El agente lista ahí, en términos estándar y con contexto ("sangrado vaginal en el embarazo"), **solo** los síntomas que la persona reporta. Se aplican **las mismas reglas**.
   - **No** se analizan `reply` ni `summary`, porque contienen signos de alarma en tono de consejo ("si tienes sangrado, acude…") y producirían falsos positivos constantes.
4. **El agente solo suma alarmas, nunca las quita.** La severidad final es la máxima de ambos filtros. Si el filtro 2 detecta una urgencia, se descarta la respuesta del agente.
5. **Trazabilidad:** cada alerta se guarda en el hilo con `rule_ids`, `severity`, `origin` (`usuario` | `agente`) y la fecha. Una regla detectada por los dos filtros se registra una sola vez, con origen `usuario`.
6. **Red de seguridad:** si hay una alarma prioritaria y el LLM falla, igual se muestra el mensaje fijo y se registra la alerta.
7. **Criterio conservador:** el texto se normaliza (minúsculas, sin tildes) y **no se interpretan negaciones** ("no tengo sangrado" también activa). Se prefiere un falso positivo a un falso negativo.
8. Las reglas que dependen de la población usan patrones de **contexto + signo** (p. ej., "embarazo" y "fiebre" en el mismo texto) para ser específicas.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Solo el filtro 1 (texto del usuario) | Más simple | No capta descripciones coloquiales ni el contexto dicho en mensajes anteriores |
| Revisar `summary` o `reply` del agente | No requiere un campo nuevo | Falsos positivos por los consejos que mencionan signos de alarma |
| Dejar que el LLM decida si hay alarma | Entiende mejor el lenguaje | No auditable ni reproducible; contradice el ADR 0004 |
| Lista cerrada de códigos de síntomas en lugar de texto libre (B-015) | Cruce exacto con las reglas | Más trabajo; se hará como evolución |
| Reglas en código Python | Validación con el tipado | El equipo clínico no las puede revisar fácilmente |

## Consecuencias
- ✅ Las alarmas son auditables, reproducibles y probadas: frases de referencia por regla en `tests/conversational/alarm_phrases.json`, con cada regla obligada a tener al menos 2 frases. R-01 y R-07 quedan mitigados en parte.
- ✅ El origen de cada alerta permite medir el aporte del filtro 2 y ampliar los patrones del filtro 1.
- ⚠️ Las reglas son **PROVISIONALES** (borrador generado con IA a partir de signos de alarma públicos) hasta su validación clínica: [solicitud de validación](../../01-especificacion/solicitud-validacion-alarmas.md). Riesgo R-09.
- ⚠️ Los patrones nunca cubrirán todas las formas de expresión, y el criterio conservador generará falsos positivos (p. ej., con negaciones).
- ⚠️ El mensaje fijo remite a urgencias o al 123 de forma genérica hasta tener las rutas por municipio (HU-05, DTS Caldas).

## Actualización 2026-10-10: observabilidad y cobertura
- **Hallazgo de la verificación humana:** una descripción coloquial de un sangrado no activó ninguna regla. Además, como `reported_symptoms` no se registraba, no se podía saber qué había reportado el agente.
- **Ajustes:**
  1. `reported_symptoms` se guarda en cada respuesta del asistente: `[]` si no hubo síntomas; el campo no aparece si el agente no fue consultado. También se muestra en la línea de depuración.
  2. Catálogo v0.2.0 con patrones menos literales.
  3. Prompt v4: síntomas literales y completos.
  4. Cada fallo detectado se agrega como frase de regresión en `alarm_phrases.json`.
- La dependencia de que el agente redacte el síntoma de una forma que los patrones cubran sigue existiendo. La solución de fondo es B-015 (códigos cerrados).
