# Modelo de datos

*Última actualización: 2026-10-10*

## 1. Implementado (HU-06, HU-03/04): hilos, mensajes y alertas en archivos JSON
Persistencia temporal en `data/threads/<thread_id>.json` (ADR 0006): un archivo por hilo, con sus mensajes embebidos. Detalle de los campos en el [diccionario de datos](diccionario-datos.md).

```mermaid
erDiagram
    THREAD ||--o{ MESSAGE : contiene
    THREAD ||--o{ ALERT : registra
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
    ALERT {
        list rule_ids "RN-MI-xx / RN-CV-xx"
        enum severity "urgencia_inmediata | consulta_prioritaria"
        enum origin "usuario | agente"
        datetime created_at
    }
```

Cada mensaje del asistente puede llevar un objeto `trace` (síntomas, evidencia, citas, tiempos y verificación del respaldo). La base de conocimiento (`KNOWLEDGE_ENTRY`) es un archivo versionado (`knowledge/kb/entries.jsonl`) y la traza la referencia por `entry_id`.

Las reglas de alarma no se persisten como entidad: son un catálogo versionado (`knowledge/alarm_rules.json`) y las alertas guardan sus `rule_ids`.

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
