---
description: Ejecuta el protocolo de cierre de tarea (AGENTS.md §6) con la matriz de impacto documental
---

Ejecuta el **Protocolo de cierre de tarea** de AGENTS.md §6 sobre los cambios actuales:

1. Ejecuta `git status` y `git diff` para listar qué cambió.
2. **Código** (si hay cambios en `src/` o `tests/`):
   - Revisa que cada función nueva o modificada tenga una sola responsabilidad, ≤ 25 líneas, type hints y docstring estilo Google en español.
   - Verifica la regla de dependencias hexagonal (domain no importa nada externo; application solo domain; los adapters no se importan entre sí).
   - Si existe tooling, ejecuta `ruff check`, `mypy` y `pytest`, y reporta el resultado.
3. **Matriz de impacto:** lee `docs/README.md` → *Matriz de impacto documental*. Por **cada fila** que aplique al cambio, actualiza los documentos indicados. Si una fila no aplica, no la toques.
4. Agrega la entrada en `CHANGELOG.md` → `[Unreleased]`.
5. Agrega una fila en `docs/05-ia/bitacora-verificacion-ia.md`, con el resultado `Pendiente de verificación` salvo que el usuario ya lo haya verificado.
6. Actualiza el `README.md` (tabla de estado o instrucciones) si corresponde.
7. Si apareció una convención nueva, actualiza `AGENTS.md`.
8. Entrega un resumen con: archivos de código cambiados, **documentos actualizados (con la fila de la matriz que lo motivó)** y lo que queda pendiente de verificación humana.

No hagas commit salvo que el usuario lo pida.
