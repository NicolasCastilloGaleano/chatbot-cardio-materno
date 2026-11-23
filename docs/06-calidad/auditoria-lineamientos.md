# Auditoría de cumplimiento de lineamientos

*Última actualización: 2026-11-22*

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
| C03 | ⚠️ → ✅ | `tests/conversational/` vacío | Cubierto: `alarm_phrases.json` + `test_alarm_phrases.py` (HU-03/04) |
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
| C15 | ❌ → ✅ | Sin BPMN | Cubierto: `bpmn/gestion-alerta.bpmn` + flujo Mermaid (HU-03/04); falta exportar el `.svg` |
| C16 | ✅ | R-01 a R-08 y protección de datos al día | — |

**Pendientes no delegables del equipo:** métricas de éxito del charter, roles (PO, líder técnico), responsables en la matriz de delegación del playbook y la retro del sprint 1.

### 2026-11-22: auditoría 2 (Claude Code, rama `feat/hu-16-fase1-casos`; revisión humana pendiente)
| ID | Resultado | Hallazgo | Acción propuesta |
|---|---|---|---|
| C01 | ⚠️ | `domain` y `application` limpios, pero `adapters/outbound/rag/ollama_embedder.py` importa de `adapters/outbound/llm` (`ollama_http`, `DEFAULT_KEEP_ALIVE`): un adaptador importa a otro (anterior a la HU-16) | Mover el cliente HTTP de Ollama y la constante a un módulo compartido (p. ej., `adapters/outbound/ollama_common.py`) o documentar la excepción en AGENTS.md §2 |
| C02 | ⚠️ | ruff y mypy sin errores; sin `noqa` en `src/`. Seis funciones pasan de 25 líneas: `web_app._add_chat_routes` (37), `_add_message_routes` (35), `clinician_routes.add_clinician_routes` (35, HU-16), `agent_turn.analysis_schema` (32), `rag_setup.apply_policy_overrides` (31), `settings.load_conversation_settings` (27) | Partir las tres de rutas en grupos (como `add_contact_routes`); las otras tres son datos declarativos: dividir o aceptarlas como excepción en los estándares |
| C03 | ✅ | 854 pruebas pasan sin Ollama; la HU-16 tiene pruebas por fase, incluida una de punta a punta del canal | — |
| C04 | ✅ | Sin `.env`, `data/`, bases `.db` ni `RAG_2.xlsx` versionados; `.gitignore` los cubre | — |
| C05 | ✅ | Cada commit de la HU-16 (fases 0 a 4) trae su entrada en el CHANGELOG y su fila en la bitácora; el hook lo exige | — |
| C06 | ✅ | Sin referencias obsoletas a "fase 4" o "siguiente fase" en la página, el código ni las guías; esquema v4 documentado | — |
| C07 | ✅ | ADR 0022 y 0023 con decisor humano y estado Propuesto; catálogo de alarmas marcado PROVISIONAL | El equipo y el equipo clínico deben revisarlos antes de aceptarlos |
| C08 | ⚠️ | Conventional Commits en español y fusiones `--no-ff` aprobadas. Quedan muchas ramas locales ya fusionadas o abandonadas (`feat/fase2-3-base-v2-y-etapas`, `feat/mig-05-06-base-rag2`, `docs/plan-migracion-rag2`…) | Borrar las ramas locales ya fusionadas o abandonadas (con la aprobación del usuario) |
| C09 | ✅ | Arquitectura con diagramas Mermaid, tabla de puertos al día (`CaseInbox`, `ClinicianOutbox`) y ADR hasta el 0023 | — |
| C10 | ⚠️ | La columna "Responsable" de la matriz de delegación del playbook sigue en TODO (igual que en la auditoría 1) | **No delegable:** el equipo asigna responsables |
| C11 | ⚠️ | 47 de 109 filas de la bitácora tienen el verificador en TODO; las de la HU-16 están "Pendiente de verificación" | Verificar en el PC con [el guion](../08-despliegue/prueba-escalamiento.md) y anotar el verificador |
| C12 | ✅ | `clinical_cases`, `case_addresses` y `clinician_outbox` en el modelo y el diccionario de datos | — |
| C13 | ⚠️ | `.github/workflows/ci.yml` existe (ruff, mypy, pytest); no se pudo ver la pestaña *Actions* (`gh` sin sesión en este equipo) | El usuario confirma en GitHub que la CI pasa en la rama antes de fusionar |
| C14 | ⚠️ | Solo existe `sprint-01.md`, con la retro y la fecha en TODO; el charter tiene las métricas de éxito en TODO | **No delegable:** el equipo registra los sprints siguientes, la retro con el uso de IA y las métricas |
| C15 | ⚠️ | Flujos Mermaid al día (incluido `flujo-escalamiento.md`); el único BPMN es `gestion-alerta.bpmn`, sin su `.svg`, y el escalamiento no tiene BPMN | Exportar el `.svg` y modelar el escalamiento en BPMN (demo.bpmn.io) si el equipo lo pide como entregable |
| C16 | ✅ | Protección de datos con la sección de la HU-16 (número temporal, clave, borrador) y riesgo R-14 nuevo | — |

**Pendientes no delegables del equipo:** responsables del playbook (C10), sprints, retro y métricas de éxito (C14), revisión de los ADR 0022 y 0023 y del prompt del borrador, la decisión sobre el filtro 2 durante el contacto directo, la validación clínica de las alarmas y el consentimiento (HU-01).

**Ítems que se proponen para la checklist:**
- **C17 (AGENTS.md §4, ADR 0023):** los datos personales temporales se borran a tiempo. Cómo: pruebas de purga de `case_addresses` y consulta a la base del PC tras cerrar un caso.
- **C18 (AGENTS.md §1, pruebas en otro equipo):** `pytest -m live` se ejecutó en el PC antes de cada fusión que toca el agente. Cómo: fila en la bitácora con el resultado.

**Correcciones aplicadas (2026-11-22, a pedido del usuario):**
- **C01 ⚠️ → ✅:** el cliente HTTP de Ollama y `DEFAULT_KEEP_ALIVE` pasan a `adapters/outbound/shared/ollama_http.py`; ningún adaptador importa a otro. Convención agregada en AGENTS.md §2 y en los estándares de código.
- **C02 ⚠️ → ✅:** ninguna función de `src/` pasa de 25 líneas. Se partieron el registro de rutas de la web (4 grupos) y de `/medico` (3 grupos), `analysis_schema`, `apply_policy_overrides` y `load_conversation_settings`, con una prueba nueva para `PolicyOverrides`.
