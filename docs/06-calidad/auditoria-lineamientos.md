# Auditoría de cumplimiento de lineamientos

*Última actualización: 2026-10-10*

Revisión periódica de que el proyecto sigue sus propias reglas (AGENTS.md, la [DoD](../00-gestion/definition-of-done.md) y la matriz de impacto) y los *Lineamientos Generales PI II v4*. Se ejecuta con `/auditar-lineamientos` en cada Sprint Review y se agrega una sección de resultados con fecha.

## Checklist
| ID | Fuente | Qué se verifica | Cómo se verifica |
|---|---|---|---|
| C01 | AGENTS.md §2 | Regla de dependencias hexagonal: `domain` no importa nada del proyecto ni infraestructura; `application` solo `domain`; los adaptadores no se importan entre sí | `grep` de imports por capa |
| C02 | AGENTS.md §3 | Funciones pequeñas, type hints, docstrings Google en español, sin `noqa` que oculten incumplimientos | ruff (C90, PLR, D), mypy, revisión de `noqa` |
| C03 | AGENTS.md §3 | Toda lógica nueva tiene pruebas; `tests/conversational` cubre los flujos | pytest + revisión de la trazabilidad |
| C04 | AGENTS.md §4 | No hay secretos ni datos reales versionados (`.env`, `data/threads`) | `git ls-files` + `.gitignore` |
| C05 | AGENTS.md §6 | CHANGELOG y bitácora actualizados en cada tarea con cambios de código | historial de git vs. CHANGELOG y bitácora |
| C06 | AGENTS.md §6 + matriz | Los documentos de la matriz de impacto reflejan el código (sin referencias obsoletas) | `grep` de nombres de clases o archivos eliminados en `docs/` y los README |
| C07 | AGENTS.md §5 | Las decisiones no delegables las toma un humano (ADR con decisor; reglas clínicas validadas o marcadas PROVISIONAL) | revisión de ADR y del catálogo de reglas |
| C08 | AGENTS.md §7 | Ramas, Conventional Commits, fusión aprobada por el usuario | `git log` |
| C09 | Lineamientos §3.2 | Documento de arquitectura con diagramas de componentes, flujo de datos y despliegue; ADR | `docs/02-arquitectura/` |
| C10 | Lineamientos §3.2 / §5 | Playbook de orquestación actualizado (herramientas, matriz de delegación, responsables) | `docs/05-ia/playbook-orquestacion-ia.md` |
| C11 | Lineamientos §3.3 | Bitácora de verificación: cada artefacto de IA tiene resultado y verificador | `docs/05-ia/bitacora-verificacion-ia.md` |
| C12 | Lineamientos §3.5 | Modelo y diccionario de datos de las entidades implementadas | `docs/04-datos/` |
| C13 | Lineamientos §4.7 | CI básico funcionando | `.github/workflows/ci.yml` + pestaña *Actions* |
| C14 | Lineamientos §6 | Artefactos ágiles: backlog, sprint backlog, retro con uso de IA | `docs/00-gestion/` |
| C15 | Lineamientos §3.2 / docs | BPMN y diagramas de flujo de los procesos implementados | `docs/03-procesos/` |
| C16 | Lineamientos §3.6 | Riesgos de IA y protección de datos al día con lo implementado | `docs/07-gobernanza/` |

---

## Resultados

### 2026-10-10: primera auditoría (Claude Code; revisa Nicolas Castillo Galeano)
| ID | Resultado | Hallazgo | Acción |
|---|---|---|---|
| C01 | ✅ | Las capas respetan la regla de dependencias | — |
| C02 | ⚠️ → ✅ | `ConversationService.__init__` usaba `# noqa: PLR0913` (6 parámetros) | Refactor a `ConversationConfig`; regla agregada en los estándares de código |
| C03 | ⚠️ | `tests/conversational/` vacío | Se cubre con las frases de referencia de alarmas (HU-03/04) |
| C04 | ✅ | `.env` y `data/threads/` ignorados; sin datos reales | — |
| C05 | ✅ | CHANGELOG y bitácora actualizados en HU-00 y HU-06 | — |
| C06 | ⚠️ → ✅ | `application/README.md` y `persistence/README.md` mencionaban `ConversationRepository`; el playbook decía "LLM: TODO" | Corregidos |
| C07 | ✅ | ADR 0001–0006 con decisor humano | Las reglas clínicas de HU-03/04 deben quedar marcadas PROVISIONAL |
| C08 | ⚠️ → ✅ | La DoD exigía un PR revisado por otra persona, pero hay un solo desarrollador activo | Decisión del usuario: su aprobación basta mientras trabaje solo; DoD y AGENTS.md §7 ajustados |
| C09 | ✅ | Arquitectura con diagramas y ADR 0001–0006 | — |
| C10 | ⚠️ | Columna "Responsable" de la matriz de delegación en TODO | **Pendiente del equipo** (no delegable) |
| C11 | ✅ | Todas las filas con resultado; HU-00 y HU-06 aceptadas por Nicolas | — |
| C12 | ✅ | THREAD y MESSAGE documentados | — |
| C13 | ❌ → ✅ | No existía la CI | Creado `.github/workflows/ci.yml` (ruff, mypy `src` + `tests`, pytest) |
| C14 | ❌ → ⚠️ | No había registro de sprint ni retro | Creado [sprint-01.md](../00-gestion/sprints/sprint-01.md); **la retro la llena el equipo** |
| C15 | ❌ | Sin BPMN | Se cubre con el BPMN de gestión de alerta (HU-03/04) |
| C16 | ✅ | R-01 a R-08 y protección de datos al día | — |

**Pendientes no delegables del equipo:** métricas de éxito del charter, roles (PO, líder técnico), responsables en la matriz de delegación del playbook y la retro del sprint 1.
