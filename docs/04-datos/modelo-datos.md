# Modelo de datos (preliminar)

*Última actualización: 2026-10-09*

TODO: se definirá al implementar la persistencia (pendiente de ADR sobre el motor de base de datos). Diseño en 3FN y datos personales cifrados o separados de los datos de interacción.

```mermaid
erDiagram
    USER ||--o{ CONVERSATION : inicia
    CONVERSATION ||--o{ MESSAGE : contiene
    CONVERSATION ||--o{ ALERT : genera
    USER {
        uuid id
        string channel
        string channel_user_hash
        bool consent_accepted
        datetime consent_at
    }
    CONVERSATION {
        uuid id
        string state
        string topic
        datetime started_at
    }
    MESSAGE {
        uuid id
        string direction
        text content_anonymized
        datetime created_at
    }
    ALERT {
        uuid id
        string rule_id
        string severity
        string care_route
        datetime created_at
    }
```
