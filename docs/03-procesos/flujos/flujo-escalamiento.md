# Flujo del escalamiento al profesional de salud (HU-16)

*Última actualización: 2026-11-22*

Ciclo de vida de un caso (ADR 0022) y de la dirección temporal de WhatsApp (ADR 0023). Las transiciones están en `domain/escalation.py::TRANSITIONS`.

```mermaid
stateDiagram-v2
    [*] --> pendiente: turno sin evidencia y sin alarma\n(aviso de espera; en WhatsApp se guarda la dirección)
    pendiente --> pendiente: otro turno sin evidencia\n(recordatorio; renueva el plazo)
    pendiente --> aprobada: el profesional aprueba el borrador
    pendiente --> modificada: el profesional envía su versión
    pendiente --> en_contacto: contacto directo
    en_contacto --> en_contacto: mensajes de la persona y del profesional\n(sin modelo; renueva el plazo; el filtro 1 sigue)
    en_contacto --> cerrada: el profesional cierra el contacto
    pendiente --> expirada: 24 h sin mensajes de la persona
    en_contacto --> expirada: 24 h sin mensajes de la persona
    aprobada --> [*]
    modificada --> [*]
    cerrada --> [*]
    expirada --> [*]
```

## Entrega del mensaje del profesional
```mermaid
sequenceDiagram
    participant P as Profesional (/medico)
    participant W as Proceso web
    participant DB as Base SQLite
    participant R as Proceso de WhatsApp (reenvío)
    participant U as Persona
    P->>W: aprobar, modificar o escribir
    W->>DB: cambia el estado (si no cambió antes) y guarda el mensaje en el hilo
    alt chat de consola o web
        U->>DB: lee el hilo (sondeo de la interfaz)
    else WhatsApp
        W->>DB: deja el mensaje en clinician_outbox
        R->>DB: cada OUTBOX_POLL_SECONDS toma lo pendiente
        R->>U: "*Profesional de salud:* …" desde el número del proyecto
        R->>DB: marca enviado, borra el texto y, si el caso terminó, la dirección
    end
```

Las alarmas nunca pasan por aquí: salen de inmediato, antes y durante el caso.
