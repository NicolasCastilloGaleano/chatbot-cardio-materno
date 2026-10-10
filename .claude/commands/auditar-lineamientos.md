---
description: Audita el cumplimiento de AGENTS.md, la DoD y los Lineamientos PI II, y registra los resultados con fecha
---

Ejecuta una auditoría de cumplimiento usando la checklist de `docs/06-calidad/auditoria-lineamientos.md`:

1. Lee la checklist (C01…Cnn) y, para cada ítem, aplica el método de la columna "Cómo se verifica". Usa `grep`, `git log`, `git ls-files`, `ruff`, `mypy` y `pytest` según corresponda. Revisa evidencia real; no supongas.
2. Clasifica cada ítem: ✅ conforme, ⚠️ parcial, ❌ incumple. Explica el hallazgo en una línea.
3. Agrega al final del documento una sección `### AAAA-MM-DD: auditoría N` con la tabla de resultados (ID, resultado, hallazgo, acción propuesta).
4. **No corrijas nada todavía.** Presenta al usuario los hallazgos ⚠️ y ❌ con una propuesta de corrección y pregunta cuáles aplicar.
5. Separa los pendientes **no delegables** (roles, métricas, contenido clínico, priorización), que solo puede resolver el equipo.
6. Si la checklist quedó desactualizada (p. ej., hay nuevos entregables de los lineamientos), propón agregar ítems.
