# CLAUDE.md

Las reglas del proyecto viven en AGENTS.md (fuente única). Son obligatorias:

@AGENTS.md

## Específico de Claude Code
- Al terminar una tarea con cambios, ejecutar el **Protocolo de cierre** (AGENTS.md §6) o usar `/cerrar-tarea`.
- El hook `Stop` (`.claude/hooks/check_docs.py`) bloqueará el cierre si faltan el CHANGELOG o la bitácora IA. **No hay que evadirlo**: hay que actualizar los documentos.
- Antes de implementar una funcionalidad, leer la historia de usuario y los criterios de aceptación en `docs/01-especificacion/`. Si no existen, proponerlos primero al usuario.
- En las tareas de varios pasos, mantener una lista de tareas visible e incluir la actualización documental como paso explícito.
