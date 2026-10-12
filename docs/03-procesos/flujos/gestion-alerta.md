# Flujo: gestión de alerta por signos de alarma (HU-03 / HU-04)

*Última actualización: 2026-10-11*

Comportamiento implementado ([ADR 0007](../../02-arquitectura/adr/0007-alarmas-deterministas-doble-filtro.md); desde el [ADR 0008](../../02-arquitectura/adr/0008-rag-evidencia-y-dos-llamadas.md) el "Agente LLM" se divide en una llamada de **análisis sin evidencia**, que produce `reported_symptoms`, y, si no hay urgencia, el **RAG** y la **llamada de respuesta** con evidencia. Si falla la llamada de respuesta y hay alarma, se muestra el mensaje fijo). El modelo BPMN equivalente está en [`../bpmn/gestion-alerta.bpmn`](../bpmn/gestion-alerta.bpmn).

```mermaid
flowchart TD
    A([Mensaje del usuario]) --> F1{Filtro 1:<br/>reglas sobre el texto original}
    F1 -- urgencia_inmediata --> U1[Mensaje fijo de urgencia<br/>sin consultar al LLM]
    F1 -- prioritaria o ninguna --> L[Agente LLM:<br/>JSON con reply, summary<br/>y reported_symptoms]
    L -- falla el LLM --> E{¿Hubo alarma<br/>en el filtro 1?}
    E -- sí --> U2[Mensaje fijo de la alarma prioritaria]
    E -- no --> ERR[Mensaje de error;<br/>no se guarda nada]
    L -- respuesta válida --> F2{Filtro 2:<br/>reglas sobre cada síntoma<br/>+ cruce exacto de los<br/>códigos de reported_signs}
    F2 --> S{Severidad máxima<br/>de ambos filtros}
    S -- urgencia_inmediata --> U3[Mensaje fijo de urgencia<br/>se descarta el reply del agente]
    S -- consulta_prioritaria --> P[Mensaje fijo + reply del agente]
    S -- ninguna --> N[Reply del agente]
    U1 & U2 & U3 & P --> R[(Registrar alerta en el hilo:<br/>rule_ids, severity, origin)]
    R --> M[(Registrar mensajes con thread_id)]
    N --> M
    M --> Z([Respuesta al usuario])
```

Reglas clave:
- El agente **solo suma** alarmas. Una regla detectada por los dos filtros se registra una vez, con origen `usuario`.
- No se analizan `reply` ni `summary`, porque contienen consejos que mencionan signos de alarma.
- El filtro 2 revisa **cada síntoma por separado**: el contexto de un síntoma ("en el embarazo") no se combina con el signo de otro ("fiebre en el bebé"). Así se evita el falso positivo de RN-MI-07 del 2026-10-11.
- Desde el ADR 0012 (provisional), el filtro 2 también cruza los **códigos de signos** que marca el análisis (`reported_signs`, lista cerrada); esas alertas tienen el origen `agente_codigo`. Las dos vías solo suman.
- Una urgencia del filtro 1 queda en el hilo activo **solo si es del mismo dominio**. Si no, se cierra ese hilo y se abre uno nuevo con el dominio de la regla.
- Las reglas son PROVISIONALES hasta la validación clínica (riesgo R-09).
