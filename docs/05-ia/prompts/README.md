# Prompts del producto (versionados)

Prompts del LLM **del producto** (no los del desarrollo).

- **Ubicación en runtime:** `src/cardio_materno/prompts/`. Viven junto al código porque el programa los carga al iniciar.
- **Nombre:** `nombre_vN.md`. Un cambio de comportamiento crea una versión nueva; no se sobrescribe la anterior mientras esté en evaluación.
- Un cambio de prompt es un cambio de comportamiento: aplicar la matriz de impacto (`docs/README.md`).

## Registro
| Prompt | Versión | Usado por | Propósito | Evaluación | Validación clínica |
|---|---|---|---|---|---|
| `system_prompt_v5.md` | v5 (2026-10-10) | `ConversationService` (armado con `render_system_prompt`) | v4 + lista de **nombres exactos de los signos de alarma** del catálogo, insertada al arrancar en el marcador `{{SIGNOS_DE_ALARMA}}`; en `reported_symptoms`, si el síntoma corresponde a un signo, se escribe primero su nombre exacto y luego el contexto (puente hacia B-015) | Automática: prompt renderizado sin marcadores, cada regla coincide con su nombre; pendiente: guion en el PC de pruebas | ❌ Pendiente |
| `system_prompt_v4.md` | v4 (2026-10-10), **reemplazado por v5** | `ConversationService` | v3 + `reported_symptoms` **literal y completo** (qué, dónde, cómo, a quién, contexto); ejemplo de traducción de expresiones coloquiales ("agüita rosada por abajo, tengo 7 meses" → "secreción vaginal rosada en el embarazo de 7 meses"); lista no vacía si la persona describe algo en su cuerpo. Motivado por el incidente del 2026-10-10 | Automática (Ollama simulado); pendiente: guion en el PC de pruebas | ❌ Pendiente |
| `system_prompt_v3.md` | v3 (2026-10-10), **reemplazado por v4** | `ConversationService` (HU-06 + HU-03/04) | v2 + campo `reported_symptoms`: solo los síntomas que la persona reporta, en términos estándar y con contexto ("sangrado vaginal en el embarazo"), sin consejos ni hipótesis (filtro 2, ADR 0007) | Automática con un Ollama simulado; pendiente: guion en el PC de pruebas | ❌ Pendiente |
| `system_prompt_v2.md` | v2 (2026-10-10), **reemplazado por v3** | `ConversationService` (HU-06) | v1 + respuesta obligatoria en JSON (`thread_action`, `domain`, `summary`, `reply`), criterios para continuar o abrir un hilo, definición de dominios y resumen sin datos personales | Automática con un Ollama simulado + guion manual en el PC de pruebas (2026-10-10): decisiones de hilo y resúmenes correctos | ❌ Pendiente |
| `system_prompt_v1.md` | v1 (2026-10-10), **reemplazado por v2** | `ChatService` (HU-00, eliminado) | Rol de teleorientación, no diagnosticar ni medicar, español sencillo, remitir a urgencias ante signos graves, no pedir datos personales | Pendiente: prueba manual en el PC de pruebas | ❌ Pendiente (los ejemplos de signos graves son provisionales) |

## Marcadores
| Marcador | Lo reemplaza | Con |
|---|---|---|
| `{{SIGNOS_DE_ALARMA}}` | `application/alarm_policy.py::render_system_prompt` (al arrancar, en `bootstrap/main.py`) | Lista con viñetas de los nombres (`sign`) de las reglas del catálogo cargado |
