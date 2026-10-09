# ADR 0001: Arquitectura hexagonal en un monolito modular

- **Estado:** Aceptado
- **Fecha:** 2026-10-09
- **Decisores:** equipo de desarrollo (propuesta asistida por Claude Code, aprobada por el equipo)

## Contexto
- Los lineamientos de PI II piden un patrón arquitectónico justificado (Clean, Hexagonal u otro).
- El chatbot debe funcionar en tres canales sucesivos (consola → Telegram → WhatsApp), con un LLM y un RAG cuyo proveedor puede cambiar.
- Las reglas clínicas deben estar aisladas y ser verificables.

## Decisión
Usar **arquitectura hexagonal (puertos y adaptadores)** en un **monolito modular**:
- `domain`: entidades y reglas clínicas puras.
- `application`: casos de uso, máquina de estados y puertos.
- `adapters/inbound` y `adapters/outbound`.
- `bootstrap`: composition root.

Las dependencias van solo hacia adentro.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Clean Architecture completa (4 capas, CQRS) | Muy estructurada; es la referencia de los lineamientos | Exceso de ceremonia para un MVP de un solo servicio |
| Monolito en capas tradicional (MVC) | Simple | Acopla el dominio al framework y al canal; difícil cambiar de canal o de LLM |
| Microservicios | Escalabilidad independiente | Complejidad operativa injustificada para un TRL 5 |
| Frameworks de chatbot (Rasa, Botpress) | Funcionalidad conversacional lista | Reglas clínicas atadas al framework; menos control y trazabilidad |

## Consecuencias
- ✅ Los canales y el LLM son intercambiables, el dominio es testeable sin infraestructura y los límites para los agentes de IA quedan claros.
- ⚠️ Hay más archivos e interfaces que en un script simple, lo que exige disciplina (AGENTS.md §2).
- Se puede separar más adelante en servicios si hiciera falta, porque los límites ya existen.
