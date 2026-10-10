# Flujo conversacional general (borrador)

*Última actualización: 2026-10-10*

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

## Turno implementado: hilos conversacionales (HU-06, ADR 0006)
Este es el comportamiento **actual** del prototipo. El diagrama de estados de arriba es el objetivo e incluye etapas que aún no existen: consentimiento y alarmas.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant C as ConsoleChat
    participant S as ConversationService
    participant R as ThreadRepository (JSON)
    participant L as Agente (Ollama)
    U->>C: mensaje
    C->>S: send(texto)
    S->>R: hilo activo + últimos N mensajes
    S->>L: prompt v2 + JSON del hilo (o "sin hilo") + N mensajes + mensaje nuevo
    L-->>S: {thread_action, domain, summary, reply}
    S->>S: validar JSON (si es inválido → error, no se guarda nada)
    alt sin hilo activo o thread_action = "nuevo"
        S->>R: cerrar el hilo actual (si existe)
        S->>R: crear hilo nuevo (UUID, domain, summary, abierto)
    else thread_action = "continuar"
        S->>R: actualizar domain y summary del hilo
    end
    S->>R: guardar mensaje del usuario y respuesta con thread_id
    S-->>C: respuesta + estado del hilo
    C-->>U: respuesta y línea [hilo … | dominio | estado | nuevo/continúa]
    Note over U,C: "salir" → se cierra el hilo activo
```
