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

## Turno implementado (HU-06 + HU-03/04 + HU-02; ADR 0006, 0007, 0008)
Este es el comportamiento **actual** del prototipo. El diagrama de estados de arriba es el objetivo e incluye etapas que aún no existen, como el consentimiento.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant S as ConversationService
    participant A as Reglas de alarma
    participant L1 as Agente · análisis
    participant K as RAG (KnowledgeRetriever)
    participant L2 as Agente · respuesta
    participant R as ThreadRepository (JSON)
    U->>S: mensaje
    S->>A: filtro 1 (texto original)
    alt urgencia inmediata
        S-->>U: mensaje fijo 🚨 (sin LLM, sin RAG)
    else prioritaria o ninguna
        S->>L1: prompt de análisis + JSON del hilo + últimos N mensajes + mensaje (SIN evidencia)
        L1-->>S: {thread_action, domain, summary, reported_symptoms, scope, scope_reason}
        S->>A: filtro 2 (reported_symptoms)
        alt urgencia inmediata
            S-->>U: mensaje fijo 🚨 (sin RAG, sin llamada 2)
        else sin alarma y scope = fuera_de_alcance (todo el mensaje es ajeno)
            S-->>U: mensaje fijo de alcance (sin RAG, sin llamada 2, NO se registra)
        else sin alarma y scope = conversacional (saludo, gracias)
            S->>L2: prompt de respuesta + MENSAJE CONVERSACIONAL (sin RAG)
            L2-->>S: {reply}
            S-->>U: saludo / presentación del servicio
        else en alcance (o con alarma prioritaria)
            S->>K: consulta = mensaje + resumen + síntomas (dominio del análisis)
            K-->>S: evidencia [E1..E3] o insuficiente / no disponible
            S->>L2: prompt de respuesta + caso + últimos N mensajes + EVIDENCIA + mensaje
            L2-->>S: {reply, evidence_ids ⊆ ofrecidas}
            S-->>U: (mensaje fijo ⚠️ si prioritaria) + reply
        end
    end
    S->>R: actualizar o abrir hilo · mensajes con thread_id y trace · alertas
    Note over U,S: "salir" → se cierra el hilo activo
```
