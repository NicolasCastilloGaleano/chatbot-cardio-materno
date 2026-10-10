# Playbook de orquestación de IA

*Última actualización: 2026-10-09*

Documenta cómo el equipo usa agentes de IA en el desarrollo: qué se delega, con qué herramienta, con qué entrada y qué verificación humana es obligatoria (Lineamientos §3.2 y §5). Se revisa en cada Sprint Planning.

## 1. Principios
1. Ningún artefacto generado por IA entra a `main` sin revisión humana registrada en la [bitácora](bitacora-verificacion-ia.md).
2. Los agentes trabajan bajo las reglas de [AGENTS.md](../../AGENTS.md); el hook `Stop` obliga a actualizar la documentación.
3. No se ingresan datos personales ni datos reales de la comunidad o de los aliados a servicios de IA externos.
4. Las decisiones de arquitectura, alcance, contenido clínico y relación con los aliados **no se delegan**.
5. Ante la duda sobre si algo es delegable, se trata como no delegable.

## 2. Matriz de delegación
| Tarea | Herramienta / agente | Entrada | Verificación humana obligatoria | Responsable |
|---|---|---|---|---|
| Estructura del repositorio y documentación base | Claude Code | Lineamientos PI II + propuesta del proyecto | Revisión de AGENTS.md y de los ADR por el equipo | TODO |
| Implementación de casos de uso y adaptadores | Claude Code | HU + criterios de aceptación + AGENTS.md | Code review + pruebas pasando | TODO |
| Pruebas unitarias y conversacionales | Claude Code | Criterios de aceptación en Gherkin | Revisar que las pruebas validen el criterio (no triviales) | TODO |
| Redacción de documentación técnica | Claude Code | Código + matriz de impacto | Lectura y prueba de las instrucciones en un entorno limpio | TODO |
| Prompts del LLM del producto | Claude Code (borrador) | Reglas RN-xx + guía de tono cultural | Evaluación con conversaciones de referencia + revisión clínica | TODO |
| Reglas clínicas y signos de alarma | Claude Code **solo redacta un borrador PROVISIONAL** (patrones y mensajes) a partir de fuentes públicas | Signos de alarma públicos (MinSalud, OPS, AIEPI) | **Validación clínica obligatoria** antes de usar con usuarios ([solicitud](../01-especificacion/solicitud-validacion-alarmas.md)); la decisión final es del equipo clínico | Equipo clínico |
| Decisiones de arquitectura y stack | **No delegable** (la IA propone opciones) | — | ADR firmado por el equipo | Todo el equipo |
| Priorización del backlog | **No delegable** | — | Reunión con los aliados | Product Owner |

## 3. Protocolo de verificación
1. Todo artefacto de IA queda como **"pendiente de verificación"** en la bitácora.
2. Código: pruebas automatizadas, CI en verde, ruff/mypy y revisión humana. Mientras Nicolas sea el único desarrollador activo, su verificación basta para fusionar; cuando se unan más integrantes, revisa alguien distinto a quien generó el cambio.
3. Contenido clínico: validación por el equipo clínico contra la fuente citada.
4. Documentación: seguir los pasos en un entorno limpio.
5. Se registra el resultado (aceptado, aceptado con ajustes o rechazado), con fecha y responsable.

## 4. Herramientas
| Uso | Herramienta |
|---|---|
| Codificación, pruebas y documentación | Claude Code (con AGENTS.md + hooks) |
| LLM del producto | Ollama local con `mistral-small3.1:24b` (ADR 0005) |
| Integración continua | GitHub Actions: ruff, mypy, pytest (`.github/workflows/ci.yml`) |

## 5. Incidentes
Si un agente introduce un riesgo (secretos expuestos, una regla clínica alterada, PII en los logs), se descarta el artefacto, se registra el incidente en la bitácora, se revisa el prompt y se comenta en la retrospectiva.
