# Sprint 1: prototipo por consola

*Última actualización: 2026-10-10*

| Campo | Valor |
|---|---|
| Fechas | 2026-10-09 → TODO (fin del sprint) |
| Objetivo | Prototipo funcional por consola para la demo: conversación con el LLM local, hilos con resumen y alarmas deterministas |
| Equipo activo | Nicolas Castillo Galeano (desarrollo y verificación). Juan Felipe Montanchez Botina y Santiago Silva Guarnizo se unen más adelante |

## Sprint Backlog
| Ítem | HU | Estado | Delegado a IA | Verificación humana |
|---|---|---|---|---|
| B-001 Estructura, reglas y documentación base | — | ✅ | Claude Code | Nicolas revisó AGENTS.md y los ADR |
| B-012 Chat por consola con Ollama | HU-00 | ✅ | Claude Code | Prueba en el PC de pruebas |
| B-013 Hilos conversacionales con resumen | HU-06 | ✅ | Claude Code | Guion en el PC de pruebas |
| B-004 / B-005 Alarmas deterministas (doble filtro) | HU-03, HU-04 | ✅ (técnico) | Claude Code (código y borrador PROVISIONAL de reglas) | Pruebas + PC de pruebas; **validación clínica pendiente** |
| Auditoría de lineamientos + CI | — | ✅ |
| B-008 RAG + separación análisis/respuesta | HU-02 | 🔄 | Claude Code (código, exportación de la base, prompts) | Pruebas + punta a punta simulada; pendiente: guion y `pytest -m live` en el PC de pruebas | Claude Code | Revisión de Nicolas |

## Planning: decisiones del equipo (no delegadas)
- Stack Python + FastAPI y arquitectura hexagonal (ADR 0001, 0002).
- Canales progresivos: consola → Telegram → WhatsApp (ADR 0003).
- Ollama local con `mistral-small3.1:24b` (ADR 0005).
- Hilos con resumen y persistencia en archivos JSON (ADR 0006).
- `current_focus` diferido (B-014); doble filtro de alarmas con `reported_symptoms` (propuesta de Nicolas).

## Review
TODO: fecha y asistentes. Demo prevista: conversación por consola con hilos y alarmas.

## Retrospectiva (la completa el equipo)
> Los lineamientos piden revisar explícitamente qué usos de IA funcionaron, cuáles generaron riesgo y qué se ajustará.

| Pregunta | Respuesta |
|---|---|
| ¿Qué usos de IA funcionaron bien? | TODO |
| ¿Qué usos de IA generaron riesgo o retrabajo? | TODO |
| ¿Qué ajustaremos en el siguiente sprint? | TODO |

Insumos sugeridos (de la bitácora): la IA generó código, pruebas y documentación con verificación humana en cada incremento. El hook documental mantuvo el CHANGELOG y la bitácora al día. La primera auditoría encontró desactualizaciones menores en los README y la falta de CI, y ya se corrigieron.
