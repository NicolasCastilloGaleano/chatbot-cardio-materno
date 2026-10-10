# Prompts del producto (versionados)

Prompts del LLM **del producto** (no los del desarrollo).

- **Ubicación en runtime:** `src/cardio_materno/prompts/`. Viven junto al código porque el programa los carga al iniciar.
- **Nombre:** `nombre_vN.md`. Un cambio de comportamiento crea una versión nueva; no se sobrescribe la anterior mientras esté en evaluación.
- Un cambio de prompt es un cambio de comportamiento: aplicar la matriz de impacto (`docs/README.md`).

## Registro
| Prompt | Versión | Usado por | Propósito | Evaluación | Validación clínica |
|---|---|---|---|---|---|
| `system_prompt_v2.md` | v2 (2026-10-10) | `ConversationService` (HU-06) | v1 + respuesta obligatoria en JSON (`thread_action`, `domain`, `summary`, `reply`), criterios para continuar o abrir un hilo, definición de dominios y resumen sin datos personales | Automática con un Ollama simulado + guion manual en el PC de pruebas (2026-10-10): decisiones de hilo y resúmenes correctos | ❌ Pendiente |
| `system_prompt_v1.md` | v1 (2026-10-10), **reemplazado por v2** | `ChatService` (HU-00, eliminado) | Rol de teleorientación, no diagnosticar ni medicar, español sencillo, remitir a urgencias ante signos graves, no pedir datos personales | Pendiente: prueba manual en el PC de pruebas | ❌ Pendiente (los ejemplos de signos graves son provisionales) |
