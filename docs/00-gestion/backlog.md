# Product Backlog

*Última actualización: 2026-10-10*

Priorizado por el Product Owner con los aliados (decisión **no delegable** a la IA). Cada ítem se enlaza con su historia de usuario (HU) en `../01-especificacion/historias-usuario.md`.

| ID | Ítem | HU | Prioridad | Sprint | Estado |
|---|---|---|---|---|---|
| B-001 | Estructura del repositorio, reglas y documentación base | — | Alta | 0 | ✅ Hecho |
| B-012 | Chat libre por consola con Ollama (prototipo técnico) | HU-00 | Alta | 1 | ✅ Hecho |
| B-013 | Hilos conversacionales con resumen y respuesta estructurada del agente | HU-06 | Alta | 1 | ✅ Hecho |
| B-002 | Especificación ejecutable v1 con signos de alarma validados clínicamente | — | Alta | — | ⏳ |
| B-003 | Flujo conversacional mínimo por consola (saludo → consentimiento → tema → orientación) | HU-01, HU-02 | Alta | — | ⏳ |
| B-004 | Detección determinista de signos de alarma materno‑infantiles | HU-03 | Alta | — | ⏳ |
| B-005 | Detección determinista de signos de alarma cardiovasculares | HU-04 | Alta | — | ⏳ |
| B-006 | Direccionamiento a rutas de atención | HU-05 | Alta | — | ⏳ |
| B-007 | Integración del LLM para interpretar y redactar (con guardrails) | HU-02 | Media | — | ⏳ |
| B-008 | RAG sobre la base de conocimiento curada | HU-02 | Media | — | ⏳ |
| B-009 | Adaptador Telegram (multiusuario) | — | Media | — | ⏳ |
| B-010 | Adaptador WhatsApp | — | Media | — | ⏳ |
| B-011 | Panel o registro de métricas anonimizadas | — | Baja | — | ⏳ |
| B-014 | Foco actual del hilo: campo `current_focus` en el JSON del agente, separado del `summary` (ver nota) | HU-06 | Media | — | ⏳ Diferido |

## Notas de ítems

### B-014: Foco actual del hilo (`current_focus`)
- **Idea (Nicolas Castillo Galeano, 2026-10-10):** el `summary` debe ser general (el caso y cómo ha ido la conversación). Aparte, conviene registrar qué se está tratando *ahora mismo*. Ejemplo: en un hilo largo sobre acidez en el embarazo, los últimos mensajes giran en torno a una comida concreta, y el foco sería "si puede comer piña y cítricos con la acidez".
- **Propuesta técnica:** un campo propio `current_focus` en el JSON del agente, validado como obligatorio y no vacío. Se reemplaza en cada turno y se muestra en la línea de depuración. Se prefiere a una frase al final del `summary` porque es verificable y mantiene limpio el resumen.
- **Por qué se difiere:** en la consola los últimos `THREAD_CONTEXT_MESSAGES` (6) mensajes ya le dan al agente el foco reciente, y en las pruebas de la HU-06 no aparecieron fallos de continuidad. Cambiar el prompt validado ahora agrega riesgo sin un beneficio visible para la demo.
- **Disparadores para retomarlo:** (1) al implementar Telegram o WhatsApp, donde los hilos son más largos y se retoman tras una pausa; (2) si en las pruebas el agente corta hilos que deberían continuar u olvida el tema reciente.
- **Impacto estimado:** esquema y validación del turno, entidad del hilo, archivo JSON, prompt v3, pruebas, criterio en la HU-06, nota en el ADR 0006, diccionario de datos.
