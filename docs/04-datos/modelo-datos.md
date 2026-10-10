# Modelo de datos

*Última actualización: 2026-10-10*

## 1. Implementado (HU-06): hilos y mensajes en archivos JSON
Persistencia temporal en `data/threads/<thread_id>.json` (ADR 0006): un archivo por hilo, con sus mensajes embebidos. Detalle de los campos en el [diccionario de datos](diccionario-datos.md).

```mermaid
erDiagram
    THREAD ||--o{ MESSAGE : contiene
    THREAD {
        uuid id PK
        enum domain "materno_infantil | cardiovascular | ninguno"
        string summary
        enum status "abierto | cerrado"
        datetime created_at
        datetime updated_at
    }
    MESSAGE {
        uuid thread_id FK
        enum role "user | assistant"
        text content
        datetime created_at
    }
```

## 2. Objetivo (cuando se migre a base de datos para Telegram/WhatsApp)
Diseño en 3FN, con los datos personales cifrados o separados de los datos de interacción.

```mermaid
erDiagram
    USER ||--o{ THREAD : abre
    THREAD ||--o{ MESSAGE : contiene
    THREAD ||--o{ ALERT : genera
    USER {
        uuid id
        string channel
        string channel_user_hash
        bool consent_accepted
        datetime consent_at
    }
    THREAD {
        uuid id
        uuid user_id
        string domain
        string summary
        string status
        datetime created_at
        datetime updated_at
    }
    MESSAGE {
        uuid id
        uuid thread_id
        string role
        text content_anonymized
        datetime created_at
    }
    ALERT {
        uuid id
        uuid thread_id
        string rule_id
        string severity
        string care_route
        datetime created_at
    }
```
