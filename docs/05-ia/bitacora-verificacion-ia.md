# Bitácora de verificación de artefactos generados por IA

Registro **acumulativo** (Lineamientos §3.3). Se agrega **una fila por tarea** que modifique el repositorio. El hook `Stop` exige que este archivo cambie cuando cambian `src/`, `tests/` o `knowledge/`.

Valores de resultado: `Pendiente de verificación` · `Aceptado` · `Aceptado con ajustes` · `Rechazado`. Riesgo: `Bajo` · `Medio` · `Alto`.

| Fecha | Tarea delegada | Herramienta | Artefactos | Verificación realizada | Resultado | Riesgo | Verificó |
|---|---|---|---|---|---|---|---|
| 2026-10-09 | Estructura inicial del repositorio, reglas (AGENTS.md), documentación base, ADR 0001–0004, hook de verificación documental | Claude Code (Opus 5.5) | Repositorio completo (commit inicial) | Prueba manual del hook (bloquea y permite); el usuario revisó AGENTS.md y los ADR | Aceptado | Bajo | Nicolas Castillo Galeano |
| 2026-10-10 | HU-00: chat por consola con Ollama (código, pruebas, ADR 0005, docs) | Claude Code (Opus 5.5) | `src/cardio_materno/**`, `tests/unit/*`, `run_console.py`, docs | Automática: 29 pruebas, ruff y mypy --strict en verde; ejecución de punta a punta contra un servidor Ollama simulado. **Pendiente:** prueba manual con `mistral-small3.1:24b` en el PC de pruebas | Pendiente de verificación | Medio (R-07: sin reglas de alarma) | TODO |
