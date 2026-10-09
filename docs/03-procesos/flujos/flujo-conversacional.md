# Flujo conversacional general (borrador)

*Última actualización: 2026-10-09*

Este flujo corresponde a la máquina de estados que se implementará en `application/`. Cualquier cambio en los estados o las transiciones debe reflejarse aquí **y** en el BPMN (`../bpmn/`).

```mermaid
stateDiagram-v2
    [*] --> Bienvenida
    Bienvenida --> Consentimiento: muestra aviso de teleorientación
    Consentimiento --> SeleccionTema: acepta
    Consentimiento --> Fin: no acepta
    SeleccionTema --> Conversacion: materno-infantil / cardiovascular
    Conversacion --> EvaluacionAlarma: cada mensaje
    EvaluacionAlarma --> Alerta: signo de alarma (regla determinista)
    EvaluacionAlarma --> Orientacion: sin alarma
    Alerta --> RutaAtencion
    RutaAtencion --> Conversacion
    Orientacion --> Conversacion
    Conversacion --> Fin: el usuario termina
    Fin --> [*]
```

TODO: detallar los subflujos por tema (embarazo, posparto, recién nacido, menor de 5 años, riesgo cardiovascular).
