# Documento de arquitectura

*Última actualización: 2026-10-10*

## 1. Patrón arquitectónico
**Arquitectura hexagonal (puertos y adaptadores) en un monolito modular.** Justificación en [ADR 0001](adr/0001-arquitectura-hexagonal.md).

El núcleo (dominio + aplicación) no conoce el canal ni el proveedor de LLM. Así se puede:
- probar el flujo completo por **consola**, y luego conectar **Telegram** y **WhatsApp** sin tocar el núcleo ([ADR 0003](adr/0003-canales-progresivos.md));
- cambiar de proveedor de LLM o de base de datos cambiando solo un adaptador;
- mantener las reglas clínicas aisladas, deterministas y 100 % testeables ([ADR 0004](adr/0004-reglas-deterministas-vs-llm.md)).

## 2. Diagrama de componentes
```mermaid
flowchart LR
    subgraph IN[Adaptadores de entrada]
        CON[Consola]
        TG[Telegram]
        WA[WhatsApp webhook]
        API[API FastAPI / health]
    end
    subgraph CORE[Núcleo]
        subgraph APP[application]
            UC[Casos de uso<br/>HandleIncomingMessage]
            FSM[Máquina de estados<br/>conversacional]
            P[(Puertos)]
        end
        subgraph DOM[domain]
            ALARM[Detector de signos<br/>de alarma - reglas]
            ROUTE[Rutas de atención]
            ENT[Entidades:<br/>Conversation, User, Alert]
        end
    end
    subgraph OUT[Adaptadores de salida]
        LLM[LLM: NLU + redacción]
        RAG[RAG: base de conocimiento]
        DB[Persistencia]
        NOTIF[Notificaciones / alertas]
    end
    CON & TG & WA & API --> UC
    UC --> FSM --> ALARM & ROUTE
    UC --> P
    P -.implementa.- LLM & RAG & DB & NOTIF
```

## 3. Flujo de datos de un mensaje
```mermaid
sequenceDiagram
    participant U as Usuario
    participant C as Adaptador de canal
    participant A as Caso de uso
    participant D as Dominio (reglas)
    participant L as LLM (puerto)
    participant R as RAG (puerto)
    U->>C: mensaje
    C->>A: IncomingMessage (normalizado, sin datos del canal)
    A->>A: anonimizar texto (sin PII)
    A->>L: interpretar intención y extraer síntomas
    L-->>A: intención + síntomas estructurados
    A->>D: evaluar signos de alarma (determinista)
    alt hay alarma
        D-->>A: ALARMA + ruta de atención
        A-->>C: mensaje de urgencia (plantilla fija) + ruta
    else sin alarma
        A->>R: recuperar contenido validado
        A->>L: redactar respuesta con contexto + guardrails
        A-->>C: orientación + aviso de teleorientación
    end
    C-->>U: respuesta
```

## 4. Puertos y adaptadores
| Puerto | Responsabilidad | Adaptadores |
|---|---|---|
| `MessageChannel` | Enviar respuestas al usuario | console, telegram, whatsapp |
| `LanguageModel` (`application/ports/language_model.py`) | Interpretar intención y redactar | ✅ `OllamaLanguageModel` (`adapters/outbound/llm/`, [ADR 0005](adr/0005-ollama-local-como-llm.md)) |
| `KnowledgeRetriever` | Recuperar contenido validado | TODO: vector store (ADR pendiente) |
| `ConversationRepository` | Persistir el estado de la conversación | memoria (consola), TODO: BD |
| `AlertNotifier` | Registrar o notificar alertas | log (inicial), TODO |

## 4.1 Estado implementado (HU-00, prototipo técnico)
Por ahora existe el camino mínimo: consola → caso de uso → Ollama. Todavía no hay detección de alarmas (riesgo R-07).
```mermaid
flowchart LR
    U[Usuario en consola] --> CC[ConsoleChat<br/>adapters/inbound/console]
    CC --> CS[ChatService<br/>application<br/>historial en memoria + prompt de sistema]
    CS --> LM{{Puerto LanguageModel}}
    LM -.-> OL[OllamaLanguageModel<br/>adapters/outbound/llm]
    OL -- HTTP /api/chat --> OLL[(Ollama local<br/>mistral-small3.1:24b)]
    B[bootstrap/main.py<br/>.env + verificación /api/tags] -. arma .-> CC & CS & OL
```
- El prompt de sistema está versionado en `src/cardio_materno/prompts/system_prompt_v1.md`.
- El historial se limita a `MAX_HISTORY_MESSAGES` (20) mensajes por sesión y vive solo en memoria.
- Los errores de Ollama se traducen a `LanguageModelError` con un mensaje en español. La consola los muestra y sigue funcionando.

## 5. Stack
Python 3.12+, FastAPI, pytest, ruff, mypy. Justificación en [ADR 0002](adr/0002-python-fastapi.md). LLM: Ollama local ([ADR 0005](adr/0005-ollama-local-como-llm.md)). El chat de consola no tiene dependencias de ejecución (solo librería estándar). Vector store y base de datos: pendientes de ADR.

## 6. Diagrama de despliegue (objetivo)
```mermaid
flowchart TB
    subgraph Docker Compose
        APP[app: FastAPI + núcleo]
        DB[(Base de datos)]
        VEC[(Vector store)]
    end
    WA[WhatsApp Cloud API] -- webhook HTTPS --> APP
    TG[Telegram Bot API] -- polling/webhook --> APP
    APP --> LLMAPI[Proveedor LLM]
    APP --> DB
    APP --> VEC
```
TODO: definir el entorno de pruebas (servidor, HTTPS, dominio).
