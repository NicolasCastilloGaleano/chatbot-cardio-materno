# Modelo de datos

*Última actualización: 2026-10-17 (HU-09, ADR 0015)*

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

## 2. Implementado (HU-09, fase 2): usuarios e hilos por usuario en SQLite
Base `DATABASE_PATH` (por defecto `data/cardio_materno.db`, ignorada por git), esquema versionado con `PRAGMA user_version` (ADR 0015). Adaptadores en `adapters/outbound/persistence/sqlite_*.py`. La consola y la web siguen con JSON (§1); el canal de WhatsApp (fase 3) usará esta base.

```mermaid
erDiagram
    USER ||--o{ CHANNEL_IDENTITY : "se identifica con"
    USER ||--o{ THREAD : "abre (máximo uno abierto)"
    THREAD ||--o{ MESSAGE : contiene
    THREAD ||--o{ ALERT : registra
    USER ||--o{ INBOUND_EVENT : envía
    USER ||--o{ OUTBOUND_MESSAGE : recibe
    USER {
        uuid id PK
        datetime created_at
        datetime last_seen_at
        enum consent_status "pendiente | aceptado | rechazado"
        datetime consent_at
    }
    CHANNEL_IDENTITY {
        enum channel PK "consola | web | telegram | whatsapp"
        string channel_user_hash PK "HMAC-SHA256, nunca el teléfono"
        uuid user_id FK
        datetime created_at
    }
    THREAD {
        uuid id PK
        uuid user_id FK "NULL para consola/web"
        enum domain
        string summary
        enum status "abierto | cerrado"
        datetime created_at
        datetime updated_at
        datetime last_activity_at "para el cierre por inactividad"
    }
    MESSAGE {
        int seq PK
        uuid thread_id FK
        enum role
        text content
        datetime created_at
        json trace_json
    }
    ALERT {
        int seq PK
        uuid thread_id FK
        json rule_ids_json
        enum severity
        enum origin
        datetime created_at
    }
    INBOUND_EVENT {
        enum channel PK
        string channel_message_id PK "deduplicación"
        uuid user_id FK
        string kind
        enum status "recibido | procesando | respondido | ignorado | fallido"
        string error_code
        datetime received_at
    }
    OUTBOUND_MESSAGE {
        int seq PK
        enum channel
        uuid user_id FK
        uuid thread_id FK
        enum kind "respuesta | aviso | error"
        string channel_message_id
        datetime created_at
    }
```

Reglas:
- **Aislamiento:** el agente solo accede a los hilos a través de un `ThreadRepository` acotado a un `user_id` (`SqliteThreadRepository`); un usuario no puede leer ni escribir hilos de otro.
- **Un solo hilo abierto por usuario:** índice único parcial `one_open_thread_per_user`.
- **Sin texto en los eventos:** `inbound_events` y `outbound_messages` guardan identificadores, tipos y estados; el texto solo vive en `messages` (como en el JSON).
- **Sin datos de contacto:** no se guardan el teléfono ni el nombre de perfil (`proteccion-datos.md`).

## 3. Pendiente
- `MESSAGE.content_anonymized` (anonimizar antes de guardar), `ALERT.care_route` (HU-05) y el consentimiento (HU-01).
- Política de retención y borrado por usuario.