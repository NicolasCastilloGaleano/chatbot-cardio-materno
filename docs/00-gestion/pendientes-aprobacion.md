# Pendientes de aprobación

*Última actualización: 2026-10-12*

Lista única de lo que se **implementó para mostrar resultados** o se **propuso** y que debe decidir el equipo, según AGENTS.md §5 (decisiones que no se delegan a la IA). Nicolas Castillo Galeano decidió implementar los puntos 1 a 3 (2026-10-12) para la demostración, antes de la aprobación formal. Todo sigue siendo **PROVISIONAL** hasta que se marque aquí como aprobado.

| # | Qué se decide | Quién decide | Dónde está | Estado |
|---|---|---|---|---|
| 1 | Patrones ampliados del catálogo **v0.4.0** (RN-MI-02/03/10/12/13/14 y RN-CV-03/06): reconocen descripciones correctas que no activaban su regla. No cambian signos, severidades ni mensajes | Equipo clínico | [Solicitud de validación](../01-especificacion/solicitud-validacion-alarmas.md), sección "Cambios de la versión 0.4.0" | 🟡 Implementado para la demostración; pendiente |
| 2 | **Códigos y ejemplos coloquiales** de cada signo del catálogo (v0.5.0, B-015) | Equipo clínico | Solicitud de validación, sección "Códigos y ejemplos coloquiales de la versión 0.5.0" | 🟡 Implementado para la demostración; pendiente |
| 3 | Ratificar el **ADR 0012** (signos como códigos cerrados, en paralelo con el texto libre) | Equipo | [ADR 0012](../02-arquitectura/adr/0012-signos-reportados-como-codigos-cerrados.md) | 🟡 Aceptado provisionalmente por Nicolas e implementado para la demostración; pendiente de ratificación |
| 4 | **Frases coloquiales de prueba** (18) y la regla que debe activar cada una | Equipo clínico | `tests/live/colloquial_alarm_phrases.json`; pregunta 4 de la solicitud | ⏳ Pendiente |
| 5 | **Preguntas clínicas:** fiebre en un bebé que no es recién nacido (pregunta 2) y "no quiere" frente a "no puede" comer (pregunta 3) | Equipo clínico | Solicitud de validación | ⏳ Pendiente |
| 6 | **Modelo de cada etapa** (análisis y respuesta) y umbral del RAG | Equipo | [ADR 0011](../02-arquitectura/adr/0011-modelos-por-etapa-y-latencia.md) con las rondas del benchmark | ✅ Decidido de momento (2026-10-12): análisis `mistral-small3.1:24b`, respuesta `qwen3:8b`, umbral 0,50. Falta medir la latencia de esa combinación |
| 7 | **Vacíos de la base de conocimiento** (p. ej., alimentación con acidez, diabetes gestacional), que hoy reciben abstención | Equipo clínico y líder del proyecto | B-019 en el [backlog](backlog.md) | ⏳ Pendiente |

## Cómo se registra una decisión
1. Se anota aquí el resultado, la fecha y quién decidió.
2. Si cambia el contenido clínico, se actualizan el catálogo (`validated_by`) y la solicitud de validación. Si cambia la arquitectura, el ADR pasa a *Aceptado*.
3. Se aplica la matriz de impacto (`docs/README.md`), con su entrada en el CHANGELOG y en la bitácora.
