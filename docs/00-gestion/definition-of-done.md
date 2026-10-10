# Definition of Done (DoD)

*Última actualización: 2026-10-09*

Un ítem está **terminado** solo si cumple **todo** lo siguiente:

## Código
- [ ] Cumple los criterios de aceptación de su HU.
- [ ] Respeta la regla de dependencias hexagonal (AGENTS.md §2).
- [ ] Usa funciones pequeñas con una sola responsabilidad, type hints y docstrings estilo Google en español.
- [ ] `ruff check` y `mypy --strict` pasan sin errores.
- [ ] Tiene pruebas nuevas o actualizadas y `pytest` pasa.
- [ ] No contiene secretos, datos personales ni datos reales.

## Seguridad clínica (si aplica)
- [ ] Las reglas de alarma o de ruta están en `domain/`, son deterministas y tienen pruebas por cada signo.
- [ ] El cambio fue validado por un integrante del equipo clínico (se registra en la bitácora).

## Documentación (matriz de impacto en `docs/README.md`)
- [ ] `CHANGELOG.md` actualizado.
- [ ] Bitácora de verificación de IA actualizada.
- [ ] Documentos afectados según la matriz actualizados (HU, flujos, BPMN, arquitectura, ADR, datos, trazabilidad).
- [ ] README actualizado si cambió el estado o la forma de ejecutar.

## Revisión
- [ ] Revisión humana del código generado por IA, por un integrante del equipo. Cuando haya más de un desarrollador activo, por alguien distinto a quien generó el cambio.
- [ ] CI de GitHub Actions en verde en la rama.
- [ ] Fusión a `main` aprobada por el responsable. Hoy: verificación de Nicolas y fusión directa; con más integrantes, PR con la plantilla diligenciada.

## Auditoría periódica
- [ ] En cada Sprint Review se ejecuta `/auditar-lineamientos` ([auditoría](../06-calidad/auditoria-lineamientos.md)).
