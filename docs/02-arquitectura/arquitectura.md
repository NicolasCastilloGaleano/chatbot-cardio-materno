# Documento de arquitectura

*Última actualización: 2026-10-12 (HU-08)*

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
        API[Web local FastAPI / chat y auditoría]
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
| `LanguageModel` (`application/ports/language_model.py`) | Generar la respuesta estructurada del agente (`complete_json` con JSON Schema) | ✅ `OllamaLanguageModel` (`adapters/outbound/llm/`, [ADR 0005](adr/0005-ollama-local-como-llm.md)) |
| `KnowledgeRetriever` (`application/ports/knowledge_retriever.py`) | Recuperar evidencia de la base | ✅ `HybridRetriever` (`adapters/outbound/rag/`, [ADR 0008](adr/0008-rag-evidencia-y-dos-llamadas.md)); `UnavailableRetriever` si no hay índice |
| `Embedder` (`application/ports/embedder.py`) | Convertir textos en vectores | ✅ `OllamaEmbedder` (`/api/embed`, `qwen3-embedding:8b`) |
| `ThreadRepository` (`application/ports/thread_repository.py`) | Persistir hilos y mensajes (con `thread_id`) | ✅ `JsonFileThreadRepository` (`adapters/outbound/persistence/`, [ADR 0006](adr/0006-hilos-conversacionales-con-resumen.md)) para consola y web; ✅ `SqliteThreadRepository`, acotado a un usuario ([ADR 0015](adr/0015-persistencia-sqlite-y-usuarios.md)). Los dos cumplen el mismo contrato (`test_thread_repository_contract.py`) |
| `UserThreadStore` (`application/ports/user_thread_store.py`) | Hilo abierto de cada usuario (con su última actividad) y su repositorio acotado | ✅ `SqliteUserThreadStore` (ADR 0015) |
| `UserDirectory` (`application/ports/user_directory.py`) | Usuarios y su identidad seudonimizada por canal | ✅ `SqliteUserDirectory` (ADR 0015) |
| `ChannelLog` (`application/ports/channel_log.py`) | Deduplicar mensajes del canal y auditar lo recibido y enviado, sin texto | ✅ `SqliteChannelLog` (ADR 0014 y 0015) |
| `AlertNotifier` | Notificar alertas al equipo de salud | TODO (hoy las alertas solo se registran en el hilo vía `ThreadRepository.append_alert`) |

## 4.1 Estado implementado (HU-00, HU-06, HU-03/04, HU-02, HU-08; prototipo técnico)
El flujo puede entrar por consola o por la interfaz web local y comparte `ConversationService` → filtro 1 → **llamada de análisis (sin evidencia)** → filtro 2 → **RAG** → **llamada de respuesta (con evidencia)** → **verificación determinista del respaldo**. Sin evidencia suficiente no hay llamada de respuesta (abstención fija). Reglas de alarma PROVISIONALES (R-09).
```mermaid
flowchart LR
    U[Usuario] --> CC[Consola o interfaz web local]
    CC --> CS[ConversationService<br/>application]
    CS --> AP[AlarmPolicy<br/>filtro 1 y filtro 2<br/>texto + códigos]
    AP --> DA[domain/alarms.py]
    CS --> AN{{LanguageModel<br/>análisis}}
    CS --> KR{{KnowledgeRetriever}}
    CS --> RE{{LanguageModel<br/>respuesta}}
    CS --> TR{{ThreadRepository}}
    CS --> GR[grounded_reply<br/>verificación + literal]
    GR --> DG[domain/grounding.py]
    AN -.-> OL1[OllamaLanguageModel<br/>OLLAMA_ANALYSIS_MODEL]
    RE -.-> OL2[OllamaLanguageModel<br/>OLLAMA_REPLY_MODEL]
    KR -.-> HR[HybridRetriever<br/>coseno numpy + BM25 + RRF]
    HR --> EM{{Embedder}} -.-> OE[OllamaEmbedder<br/>qwen3-embedding:8b]
    HR --> VI[(data/kb_index<br/>embeddings.npy + manifest)]
    KB[(knowledge/kb/entries.jsonl<br/>1.600 registros)] -. run_build_kb_index .-> VI
    TR -.-> JR[JsonFileThreadRepository<br/>mensajes con trace]
    OL1 & OL2 & OE --> OLL[(Ollama local)]
```
- **Interfaz local (HU-08):** FastAPI sirve la vista y las operaciones de conversación, lista e historial. Se inicia con `python run_web.py`; `WEB_HOST`/`WEB_PORT` (`.env`, por defecto `127.0.0.1:8000`) y la configuración rechaza cualquier host que no sea local (`load_web_settings`). Las respuestas seleccionables muestran los datos de `ReplyTrace`; los `entry_id` se resuelven contra la base para mostrar pregunta y respuesta completas. El historial guardado es de solo lectura. `POST /api/session/end` cierra el hilo activo antes de iniciar otro.
- **Lectura de hilos:** `ThreadRepository.list_threads` y `all_messages` soportan auditoría sin alterar los datos persistidos. El acceso sigue limitado al repositorio local de archivos JSON.
- **Hilos por usuario (HU-09, fase 2, [ADR 0015](adr/0015-persistencia-sqlite-y-usuarios.md)):** para los canales de chat continuo se crea un `ConversationService` por mensaje con `ports.repository = UserThreadStore.scoped(user_id)` y `active_thread_id` = hilo abierto del usuario. El agente recibe el mismo contexto que en la consola (`test_conversation_per_user.py` lo compara llamada por llamada) y no puede ver hilos de otra persona. Base SQLite: `sqlite_database.py` (esquema versionado, transacciones). El canal de WhatsApp que la usa es la fase 3 ([ADR 0014](adr/0014-canal-whatsapp-cloud-api.md)).
- **Contratos** (`application/agent_turn.py`): análisis `{thread_action, domain, summary, reported_symptoms, search_query, scope, scope_reason}`; respuesta con evidencia `{sentences: [{text, evidence_id}]}`, con `evidence_id` restringido por `enum` a las etiquetas ofrecidas o `"ninguna"`; respuesta conversacional `{reply, evidence_ids: []}`.
- **Respaldo** ([ADR 0010](adr/0010-respuesta-verificada-y-abstencion-determinista.md), `application/grounded_reply.py` + `domain/grounding.py`): sin evidencia suficiente, `ABSTENTION_TEXT` sin llamar al LLM; con evidencia, cada frase citada debe estar respaldada por su registro (palabras con contenido ≥ `min_support` y todos los números); si una falla, se muestra el texto literal del registro.
- **Contexto:** `application/turn_context.py`. El análisis recibe prompt + JSON del hilo + últimos N mensajes; la respuesta recibe prompt + caso analizado + últimos N mensajes + EVIDENCIA. La evidencia nunca entra al análisis (ADR 0008).
- **Alarmas** ([ADR 0007](adr/0007-alarmas-deterministas-doble-filtro.md)): con urgencia en el filtro 1, no hay llamadas ni RAG; con urgencia en el filtro 2, no hay RAG ni llamada de respuesta. Desde el [ADR 0012](adr/0012-signos-reportados-como-codigos-cerrados.md) (provisional), el filtro 2 revisa los síntomas en texto **y** cruza de forma exacta los códigos de `reported_signs` (`AlarmPolicy.evaluate_codes`, `domain/alarms.py::rules_for_codes`); el esquema del análisis se arma con los códigos del catálogo.
- **Alcance** ([ADR 0009](adr/0009-control-de-alcance-por-intencion.md), `application/scope.py`): sin alarma, `fuera_de_alcance` da un mensaje fijo, sin RAG ni respuesta y sin registro; `conversacional` da respuesta sin RAG. Las alarmas y los síntomas reportados de nuestros dominios nunca se descartan.
- **Configuración:** todo lo ajustable vive en `.env`, ordenado por secciones (`.env.example`). Cada etapa tiene su modelo, temperatura, contexto, tiempo de espera, razonamiento y límite de tokens (`bootstrap/settings.py::load_stage_settings`, `stage_environment`). Los umbrales del RAG y de la verificación de `.env` se aplican sobre `evidence_policy.json` (`rag_setup.py::load_effective_policy`).
- **Latencia** ([ADR 0011](adr/0011-modelos-por-etapa-y-latencia.md), decidido de momento: análisis mistral-small, respuesta qwen3): embedder en CPU por defecto (`OLLAMA_EMBED_NUM_GPU=0`), `OLLAMA_KEEP_ALIVE`, precalentamiento de los modelos al arrancar (`warm_up`), límite de tokens por etapa (`OLLAMA_*_NUM_PREDICT`) y `OLLAMA_THINK`; comparación de modelos con `scripts/benchmark_models.py`. Ver [operacion.md](../08-despliegue/operacion.md).
- **Consulta de búsqueda:** `search_query` del análisis, sin el contexto ajeno; si viene vacía, mensaje + resumen + síntomas (`application/evidence.py::build_evidence_query`). Queda en la traza.
- **Datos no dichos:** `domain/grounding.py::unstated_details` marca en la traza los síntomas con números que la persona no escribió (auditoría; el filtro 2 los sigue revisando).
- **Prompts:** `prompts/analysis_prompt_v3.md` (con `{{SIGNOS_DE_ALARMA}}`) y `prompts/reply_prompt_v3.md`.
- **Traza:** cada respuesta guarda `trace` (síntomas, evidencia, citas, estado de la búsqueda, tiempos y verificación del respaldo `grounding`). Ver el [diccionario de datos](../04-datos/diccionario-datos.md).
- **Errores:** `LanguageModelError` si fallan el análisis o la respuesta. Sin alarma no se guarda nada; con alarma, se muestra el mensaje fijo. Si el RAG no está disponible, se muestra la abstención fija.

## 5. Stack
Python 3.12+, FastAPI, Uvicorn, pytest, ruff, mypy. LLM: Ollama local ([ADR 0005](adr/0005-ollama-local-como-llm.md)). RAG: índice propio con **numpy** ([ADR 0008](adr/0008-rag-evidencia-y-dos-llamadas.md)). FastAPI y Uvicorn son dependencias de ejecución para HU-08 ([ADR 0013](adr/0013-interfaz-web-local-de-auditoria.md)).

## 6. Diagrama de despliegue (objetivo)
```mermaid
flowchart TB
    subgraph Docker Compose
        APP[app: FastAPI + núcleo]
        DB[(Base de datos)]
        IDX[(Índice vectorial)]
    end
    WA[WhatsApp Cloud API] -- webhook HTTPS --> APP
    TG[Telegram Bot API] -- polling/webhook --> APP
    APP --> LLMAPI[Ollama: LLM + embeddings]
    APP --> DB
    APP --> IDX
```
TODO: definir el entorno de pruebas (servidor, HTTPS, dominio).
