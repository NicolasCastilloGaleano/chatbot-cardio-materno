# Product Backlog

*Última actualización: 2026-10-10*

Priorizado por el Product Owner con los aliados (decisión **no delegable** a la IA). Cada ítem se enlaza con su historia de usuario (HU) en `../01-especificacion/historias-usuario.md`.

| ID | Ítem | HU | Prioridad | Sprint | Estado |
|---|---|---|---|---|---|
| B-001 | Estructura del repositorio, reglas y documentación base | — | Alta | 0 | ✅ Hecho |
| B-012 | Chat libre por consola con Ollama (prototipo técnico) | HU-00 | Alta | 1 | ✅ Hecho |
| B-013 | Hilos conversacionales con resumen y respuesta estructurada del agente | HU-06 | Alta | 1 | ✅ Hecho |
| B-002 | Especificación ejecutable v1 con signos de alarma validados clínicamente | — | Alta | — | ⏳ Esperando la validación clínica ([solicitud](../01-especificacion/solicitud-validacion-alarmas.md)) |
| B-003 | Flujo conversacional mínimo por consola (saludo → consentimiento → tema → orientación) | HU-01, HU-02 | Alta | — | ⏳ |
| B-004 | Detección determinista de signos de alarma materno‑infantiles | HU-03 | Alta | 1 | 🔄 En verificación |
| B-005 | Detección determinista de signos de alarma cardiovasculares | HU-04 | Alta | 1 | 🔄 En verificación |
| B-006 | Direccionamiento a rutas de atención | HU-05 | Alta | — | ⏳ |
| B-007 | Integración del LLM para interpretar y redactar (con guardrails) | HU-02 | Media | — | ⏳ |
| B-008 | RAG sobre la base de conocimiento curada | HU-02 | Media | — | ⏳ |
| B-009 | Adaptador Telegram (multiusuario) | — | Media | — | ⏳ |
| B-010 | Adaptador WhatsApp | — | Media | — | ⏳ |
| B-011 | Panel o registro de métricas anonimizadas | — | Baja | — | ⏳ |
| B-014 | Foco actual del hilo: campo `current_focus` en el JSON del agente, separado del `summary` (ver nota) | HU-06 | Media | — | ⏳ Diferido |
| B-015 | Síntomas reportados por el agente como **códigos cerrados** del catálogo (p. ej. `SANGRADO_VAGINAL`) en lugar de texto libre | HU-03, HU-04 | Media | — | ⏳ |
| B-016 | `AlertNotifier`: avisar al equipo de salud cuando se registra una alerta | HU-03, HU-04 | Media | — | ⏳ |

## Notas de ítems

### B-014: Foco actual del hilo (`current_focus`)
- **Idea (Nicolas Castillo Galeano, 2026-10-10):** el `summary` debe ser general (el caso y cómo ha ido la conversación). Aparte, conviene registrar qué se está tratando *ahora mismo*. Ejemplo: en un hilo largo sobre acidez en el embarazo, los últimos mensajes giran en torno a una comida concreta, y el foco sería "si puede comer piña y cítricos con la acidez".
- **Propuesta técnica:** un campo propio `current_focus` en el JSON del agente, validado como obligatorio y no vacío. Se reemplaza en cada turno y se muestra en la línea de depuración. Se prefiere a una frase al final del `summary` porque es verificable y mantiene limpio el resumen.
- **Por qué se difiere:** en la consola los últimos `THREAD_CONTEXT_MESSAGES` (6) mensajes ya le dan al agente el foco reciente, y en las pruebas de la HU-06 no aparecieron fallos de continuidad. Cambiar el prompt validado ahora agrega riesgo sin un beneficio visible para la demo.
- **Disparadores para retomarlo:** (1) al implementar Telegram o WhatsApp, donde los hilos son más largos y se retoman tras una pausa; (2) si en las pruebas el agente corta hilos que deberían continuar u olvida el tema reciente.
- **Impacto estimado:** esquema y validación del turno, entidad del hilo, archivo JSON, prompt v3, pruebas, criterio en la HU-06, nota en el ADR 0006, diccionario de datos.

### B-015: Síntomas como códigos cerrados
- Hoy el agente escribe `reported_symptoms` en texto libre y las mismas regex lo revisan (filtro 2, ADR 0007).
- Evolución: el catálogo define un código por signo, el JSON Schema restringe `reported_symptoms` a esos códigos y el cruce con las reglas pasa a ser exacto, sin depender de la redacción del agente.
- Se retoma si el origen `agente` muestra fallos de cobertura o falsos positivos frecuentes.
- **Evidencia (2026-10-10):** el agente describió un sangrado como "secreción rosada por la vagina" y ningún patrón lo cubría. Se corrigió ampliando los patrones, pero confirma la fragilidad del texto libre. Prioridad sugerida: subir a Alta después de la demo.
