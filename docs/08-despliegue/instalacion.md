# Instalación y ejecución

*Última actualización: 2026-10-18 (HU-09: suscripción de la cuenta de WhatsApp Business)*

## A. PC de pruebas (Ubuntu 24.04 + Ollama)
Requisitos: **Python 3.12+**, **Git**, **[Ollama](https://ollama.com/download)** con `mistral-small3.1:24b` y `qwen3-embedding:8b`.

### Primera vez
```bash
git clone https://github.com/NicolasCastilloGaleano/chatbot-cardio-materno.git
cd chatbot-cardio-materno

# Modelos (si aún no están)
ollama pull mistral-small3.1:24b
ollama pull qwen3-embedding:8b

# Entorno virtual: Ubuntu 24.04 no permite pip sobre el Python del sistema (PEP 668)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Configuración local
cp .env.example .env

# Índice de la base de conocimiento (minutos con GPU)
.venv/bin/python run_build_kb_index.py

# Chat
.venv/bin/python run_console.py

# Interfaz web local para demostración y auditoría
.venv/bin/python run_web.py
```

### Las siguientes veces
```bash
git pull
.venv/bin/pip install -r requirements.txt     # por si cambiaron las dependencias
.venv/bin/python run_build_kb_index.py        # solo si cambió knowledge/kb/entries.jsonl o OLLAMA_EMBED_MODEL
.venv/bin/python run_console.py
# Alternativa de demostración: interfaz de chat y auditoría en http://127.0.0.1:8000
.venv/bin/python run_web.py
```
Si acabas de cambiar a una rama que incorpora dependencias nuevas, instala primero las versiones de esa rama con `.venv/bin/pip install -r requirements.txt`.
Al arrancar se muestran las reglas de alarma cargadas, los modelos de cada etapa y el estado de la base de conocimiento. Si el índice no existe o no corresponde, aparece `⚠️ RAG no disponible…` con la instrucción para reconstruirlo; el chat sigue, pero sin información de salud.

Escribe tus mensajes y presiona Enter. Para terminar, escribe `salir` (o usa Ctrl+C). Cada consulta queda en un hilo, guardado en `data/threads/<id>.json`.

### Interfaz local de chat y auditoría (HU-08)
Ejecuta `.venv/bin/python run_web.py` y abre `http://127.0.0.1:8000` (`WEB_HOST` y `WEB_PORT` en `.env`; el host solo puede ser local). La app carga los mismos modelos, reglas, RAG e hilos que la consola. Haz clic en una respuesta del asistente para inspeccionar la traza y los registros completos de evidencia. Los hilos guardados se pueden consultar en modo de solo lectura; "Nueva sesión" cierra el hilo actual. El servicio escucha solo en el equipo local; no lo expongas a una red ni lo uses con usuarios reales.

### Importar el histórico JSON (HU-10, una sola vez)
Los hilos de consola y web anteriores a la migración están en `data/threads/*.json`. Para verlos en la interfaz de auditoría, impórtalos a la base SQLite (`DATABASE_PATH`):
```bash
.venv/bin/python run_import_history.py
```
Quedan en un chat "Histórico" de solo lectura, cerrados y con sus mensajes, trazas y alertas. Repetir el comando no duplica nada. Los archivos JSON no se modifican ni se borran.
### Canal WhatsApp (HU-09, ADR 0014 y 0015)
El canal corre en el PC de pruebas (donde está Ollama). Meta envía cada mensaje a una URL pública HTTPS (el **webhook**); **ngrok** la publica y la reenvía al servidor local `run_whatsapp.py`, que escucha solo en `127.0.0.1:8001`. Cada persona tiene su usuario (identificado por un hash del número, nunca el número) y sus hilos en `data/cardio_materno.db`.

```
Teléfono ─► Meta (WhatsApp Cloud API) ─► https://<dominio>.ngrok-free.app/webhooks/whatsapp
            ▲                                   │ ngrok
            └──── respuesta (Graph API) ◄──── run_whatsapp.py (127.0.0.1:8001) ─► cola ─► agente
```

**1. Datos de la app en Meta** (developers.facebook.com → tu app → *WhatsApp → API Setup / Configuración de la API*)
1. Copia el **Phone number ID** (el identificador del número de prueba, no el número) a `WHATSAPP_PHONE_NUMBER_ID`.
2. Genera el **token de acceso temporal** (dura 24 h) y cópialo a `WHATSAPP_TOKEN`.
3. En **To / Para**, agrega y verifica con el código que llega por WhatsApp cada número del equipo que va a probar (máximo 5). El número de prueba solo conversa con esos números.
4. Opcional: "Send message" envía la plantilla `hello_world` a tu número; si llega, el token y el ID están bien.
5. En *App settings → Basic / Configuración de la app → Básica*, muestra el **App Secret** y cópialo a `WHATSAPP_APP_SECRET`.
6. Inventa dos cadenas largas y aleatorias (p. ej., `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`): una para `WHATSAPP_VERIFY_TOKEN` y otra para `USER_ID_HASH_SECRET`. Guarda una copia de `USER_ID_HASH_SECRET`: si se pierde, las personas quedan desligadas de su historial.
7. Revisa la versión de la Graph API que muestran los ejemplos del panel (p. ej., `v23.0`) y ponla en `WHATSAPP_API_VERSION`.

**2. ngrok** (una sola vez)
1. Crea una cuenta gratuita en ngrok.com e instala ngrok (`sudo snap install ngrok` o el paquete de su página).
2. `ngrok config add-authtoken <tu-token>` (el token está en el panel de ngrok).
3. En *Domains*, reclama tu **dominio estático gratuito** (p. ej., `algo.ngrok-free.app`). Así la URL no cambia entre arranques y no hay que reconfigurar Meta.

**3. Arrancar** (dos terminales, en este orden)
```bash
.venv/bin/python run_whatsapp.py                      # terminal 1: modelos, RAG, base y webhook
ngrok http --url=algo.ngrok-free.app 8001            # terminal 2: URL pública
```
Comprueba `https://algo.ngrok-free.app/health` en el navegador: debe responder `{"status":"ok"}`.

**4. Webhook en Meta** (*WhatsApp → Configuration / Configuración*), con los dos procesos corriendo
1. **Callback URL:** `https://algo.ngrok-free.app/webhooks/whatsapp`.
2. **Verify token:** el mismo valor de `WHATSAPP_VERIFY_TOKEN`.
3. "Verify and save": Meta hace un GET con `hub.challenge` y nuestro servidor lo devuelve si el token coincide. En la terminal de ngrok aparece `GET /webhooks/whatsapp 200`.
4. En **Webhook fields**, pulsa *Manage* y suscríbete a **`messages`**. Sin esto Meta no envía nada.

**4b. Suscribir la cuenta de WhatsApp Business a la app** (una sola vez; sin esto, el botón *Test* de Meta llega pero los mensajes reales no). El **WhatsApp Business Account ID** está en *API Setup*, junto al Phone number ID (no los confundas). En el PC de pruebas, primero:
```bash
TOKEN=$(grep '^WHATSAPP_TOKEN=' .env | tail -n 1 | cut -d= -f2-)
```
Luego, con tu WhatsApp Business Account ID en lugar de `123456789012345` (sin `<` `>`):
```bash
curl -X POST "https://graph.facebook.com/v23.0/123456789012345/subscribed_apps" -H "Authorization: Bearer $TOKEN"
```
Debe responder `{"success":true}`.

**5. Probar**: desde un teléfono verificado escribe "hola" al número de prueba. Verás el mensaje como leído, "escribiendo…", el aviso de espera si tarda más de 10 s y luego la respuesta. El inspector de ngrok (`http://127.0.0.1:4040`) muestra cada notificación; con *Replay* puedes reenviarla y comprobar que no se responde dos veces.

**Token permanente** (cuando el flujo funcione; el temporal vence en 24 h): en business.facebook.com → *Configuración del negocio → Usuarios del sistema*, crea un usuario del sistema (admin), asígnale la app y la cuenta de WhatsApp Business, y genera un token sin vencimiento con los permisos `whatsapp_business_messaging` y `whatsapp_business_management`. Reemplaza `WHATSAPP_TOKEN` y reinicia `run_whatsapp.py`.

**Revisar la base** (`sudo apt install sqlite3`):
```bash
sqlite3 data/cardio_materno.db "SELECT id, last_seen_at FROM users;"
sqlite3 data/cardio_materno.db "SELECT user_id, status, domain, summary FROM threads ORDER BY updated_at DESC;"
sqlite3 data/cardio_materno.db "SELECT channel_message_id, kind, status, error_code FROM inbound_events;"
```
### Líneas de depuración (con `SHOW_THREAD_DEBUG=true`)
| Línea | Qué muestra |
|---|---|
| `[hilo … \| dominio \| estado \| nuevo/continúa \| ⚠️ alertas]` | Hilo del turno y alertas (con origen `usuario` o `agente`) |
| `[síntomas reportados por el agente: …]` / `[agente no consultado: …]` | Lo que vio el filtro 2 |
| `[evidencia: E1 0.71 Categoría \| … \| citadas: E1]` | Evidencia ofrecida (puntaje y categoría) y citada. También puede decir `insuficiente (mejor 0.48)`, `no disponible` o `no se buscó` |
| `[tiempos: análisis 3.1 s · RAG 0.4 s · respuesta 6.2 s]` | Duración de cada etapa |

### Guiones de prueba
**Hilos (HU-06):**
1. `Estoy embarazada de 5 meses y tengo mucha acidez` → `[hilo … | materno_infantil | abierto | nuevo]`
2. `¿Qué puedo comer para eso?` → mismo hilo, `continúa`
3. `Otra cosa, mi papá tiene la presión alta` → otro hilo, `cardiovascular | nuevo`
4. `salir` → en `data/threads/`, los dos hilos quedan `cerrado`

**Alarmas (HU-03/HU-04):**
1. `estoy embarazada y tengo un sangrado` → solo el mensaje fijo 🚨, `RN-MI-01 urgencia_inmediata (usuario)` y `[agente no consultado…]`
2. `mi papá tiene la presión alta` → mensaje fijo ⚠️ + orientación, `RN-CV-06 consulta_prioritaria`
3. `tengo 34 semanas y desde ayer el bebé está muy quietico` → alerta `RN-MI-06 (agente)`, `[evidencia: no se buscó…]`
4. `¿qué signos de alarma hay en el embarazo?` → sin alerta y `[síntomas …: ninguno]`
5. Si una frase debería alertar y no lo hace, copia las líneas de depuración y el mensaje

**Evidencia (HU-02, ADR 0010):** con `SHOW_THREAD_DEBUG=true`. Anota los `[tiempos …]` de cada turno.
1. `¿por qué es importante controlar la presión si no me duele nada?` → respuesta con `[evidencia: … | citadas: E…]` y `[respaldo: N/N frases]` (sin "texto literal")
2. `¿qué puedo comer si tengo acidez en el embarazo?` → la base no tiene registros de alimentación: abstención (`[respaldo: abstención sin LLM …]`) o el texto literal de un registro (`[respaldo: … · texto literal del registro]`). **Nunca** consejos como jengibre, manzanilla o listas de alimentos
3. Abstención: `tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?` → mensaje fijo "No tengo información validada…", `[evidencia: insuficiente …]`, `[respaldo: abstención sin LLM …]` y **sin** tiempo de `respuesta` en `[tiempos …]`
4. `salir` y abre el JSON más reciente de `data/threads/`: la respuesta del paso 1 tiene `trace` con la evidencia ofrecida, la citada, `grounding` (frases mostradas, total, `literal`, `dropped`) y los tiempos
5. RAG no disponible: `KB_INDEX_DIR=data/no-existe .venv/bin/python run_console.py` → al arrancar aparece "⚠️ RAG no disponible…"; repite el paso 1: mensaje fijo de abstención y `[evidencia: no disponible …]`
6. Latencia: anota los `[tiempos …]` de los pasos 1 y 2. El embedder ya corre en CPU por defecto y los modelos se cargan al arrancar, así que el primer turno ya no debería ser más lento
7. Si una respuesta muestra el texto literal, copia la línea `[respaldo …]` y el `grounding.dropped` del JSON: sirven para calibrar `min_support`

**Alcance (HU-07):**
1. `¿qué opinas del fútbol?` → mensaje fijo de alcance y `[fuera de alcance: … · no se registra en el hilo]`
2. `estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas, ¿es normal?` → respuesta con evidencia (en alcance)
3. `¿quién ganó el partido? ah, y tengo la presión alta` → alerta prioritaria RN-CV-06 y, si hay evidencia suficiente, una respuesta verificada solo sobre la presión que puede decir "sobre el partido no puedo ayudarte". Con evidencia insuficiente, solo el mensaje fijo ⚠️ (ADR 0010)
4. `hola` y luego `gracias` → saludo que presenta el servicio, `[evidencia: no se buscó (mensaje conversacional)]`
5. Dentro de un hilo: `tengo acidez en el embarazo` → `¿quién ganó el partido?` → `¿y qué más puedo comer?`: el segundo recibe el mensaje fijo, el tercero dice `continúa` en el **mismo** hilo y el dominio sigue siendo `materno_infantil`
6. Seguimiento: `mi bebé tiene fiebre` → (el asistente pregunta algo) → `sí, desde ayer` → mismo hilo, `continúa`
7. Alarma con otro tema: `estaba viendo el partido y de pronto se me torció la boca y no puedo mover el brazo` → mensaje fijo de urgencia con `RN-CV-03` (filtro 1 o 2); nunca el mensaje fijo de alcance
8. `salir` y abre el JSON del hilo del paso 5: los mensajes sobre el partido no están

Si un paso no da lo esperado, copia el mensaje, la respuesta y las líneas de depuración.

**Análisis v3 (datos no dichos y consulta de búsqueda):**
1. `tengo acidez en el embarazo` → `¿y qué más puedo comer?`: **no** debe aparecer `[⚠️ datos que la persona no escribió: …]` ni semanas en `[síntomas …]`
2. Después, `mi bebé tiene fiebre`: si abre un hilo nuevo, los síntomas no incluyen la acidez y no se activa RN-MI-07
3. `¿quién ganó el partido? ah, y tengo la presión alta` → la línea `[búsqueda: …]` habla solo de la presión (sin el partido); compara la `[evidencia …]` con el guion anterior (0,50, insuficiente)

**Pruebas en vivo (sonda de recuperación, no contaminación, alcance, análisis y respaldo):**
```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -m live -s
```
Meta inicial: ≥ 13 de 16 consultas con la categoría esperada en el top-3. Además, las preguntas educativas no deben reportar síntomas y los reportes coloquiales deben activar el filtro 2.

### Variables (`.env`)
`.env.example` está ordenado en las mismas secciones. **Regla general:** una variable vacía toma su valor por defecto. En las etapas, una variable vacía toma la general (por ejemplo, `OLLAMA_REPLY_TEMPERATURE` vacía usa `OLLAMA_TEMPERATURE`). Los umbrales del RAG y de la verificación, si tienen valor, **reemplazan** los de `knowledge/evidence_policy.json`.

**1. General y servidor de Ollama**
| Variable | Por defecto | Para qué |
|---|---|---|
| `APP_ENV` / `LOG_LEVEL` / `CHANNEL` | `development` / `INFO` / `console` | Entorno, nivel de registro (lo usa `run_whatsapp.py`) y canal |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Dirección del servidor Ollama |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tiempo que Ollama mantiene cargados los modelos entre turnos |

**2. Modelos y generación (generales y por etapa, ADR 0011)**
| Variable general | Por etapa (análisis / respuesta) | Por defecto | Para qué |
|---|---|---|---|
| `OLLAMA_MODEL` | `OLLAMA_ANALYSIS_MODEL` / `OLLAMA_REPLY_MODEL` | `mistral-small3.1:24b` | Modelo (nombre de `ollama list`). **Decisión del equipo (2026-10-12):** análisis `mistral-small3.1:24b`, respuesta `qwen3:8b` |
| `OLLAMA_TEMPERATURE` | `OLLAMA_ANALYSIS_TEMPERATURE` / `OLLAMA_REPLY_TEMPERATURE` | `0.3` | Creatividad (0 = más predecible) |
| `OLLAMA_NUM_CTX` | `OLLAMA_ANALYSIS_NUM_CTX` / `OLLAMA_REPLY_NUM_CTX` | `4096` | Ventana de contexto en tokens |
| `OLLAMA_TIMEOUT_SECONDS` | `OLLAMA_ANALYSIS_TIMEOUT_SECONDS` / `OLLAMA_REPLY_TIMEOUT_SECONDS` | `180` | Espera máxima por respuesta (s) |
| `OLLAMA_THINK` | `OLLAMA_ANALYSIS_THINK` / `OLLAMA_REPLY_THINK` | (vacío = no se envía) | `false` desactiva el razonamiento de modelos como qwen3 (**obligatorio** con qwen3 en la respuesta) |
| — | `OLLAMA_ANALYSIS_NUM_PREDICT` / `OLLAMA_REPLY_NUM_PREDICT` | `600` / `500` | Máximo de tokens que genera cada etapa (`auto` = sin límite) |

**3. RAG y búsqueda de evidencia (ADR 0008)**
| Variable | Por defecto | Para qué |
|---|---|---|
| `RAG_ENABLED` | `true` | Activa la búsqueda de evidencia |
| `OLLAMA_EMBED_MODEL` | `qwen3-embedding:8b` | Modelo de embeddings (debe coincidir con el del índice) |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `120` | Espera máxima por embedding |
| `OLLAMA_EMBED_NUM_GPU` | `0` | Capas del embedder en GPU: `0` = CPU (deja la GPU al LLM), `auto` = decide Ollama |
| `EMBED_BATCH_SIZE` | `16` | Textos por lote al construir el índice |
| `KB_ENTRIES_FILE` / `KB_INDEX_DIR` | `knowledge/kb/entries.jsonl` / `data/kb_index` | Base de conocimiento e índice (derivado) |
| `EVIDENCE_POLICY_FILE` | `knowledge/evidence_policy.json` | Valores calibrados por defecto (umbral, top-k, instrucción de consulta) |
| `RAG_MIN_SIMILARITY` | (archivo: `0.50`) | Similitud mínima para que un registro cuente como evidencia (0 a 1). **0,55 → 0,50 por decisión del equipo (2026-10-12)** |
| `RAG_TOP_K` / `RAG_CANDIDATE_K` | (archivo: `3` / `12`) | Registros que se entregan al agente / candidatos antes de fusionar |

**4. Verificación del respaldo (ADR 0010)**
| Variable | Por defecto | Para qué |
|---|---|---|
| `GROUNDING_MIN_SUPPORT` | (archivo: `0.6`) | Fracción mínima de palabras de una frase que debe estar en el registro citado |
| `GROUNDING_MAX_FREE_SENTENCES` | (archivo: `2`) | Frases sin cita permitidas (preguntas de aclaración, cortesía) |
| `GROUNDING_MAX_FREE_WORDS` | (archivo: `20`) | Palabras máximas de una frase sin cita |

**5. Interfaz web local (ADR 0013)**
| Variable | Por defecto | Para qué |
|---|---|---|
| `WEB_HOST` | `127.0.0.1` | Dirección de escucha. Solo `127.0.0.1`, `localhost` o `::1`: cualquier otra impide arrancar, porque la interfaz muestra datos de salud sin autenticación |
| `WEB_PORT` | `8000` | Puerto |

**6. Alarmas, hilos y consola**
| Variable | Por defecto | Para qué |
|---|---|---|
| `ALARM_RULES_FILE` | `knowledge/alarm_rules.json` | Catálogo de reglas de alarma (PROVISIONAL) |
| `THREAD_CONTEXT_MESSAGES` | `6` | Mensajes recientes del hilo que se envían al agente |
| `SHOW_THREAD_DEBUG` | `true` | Muestra las líneas de depuración |
| `THREADS_DIR` | `data/threads` | Carpeta de los JSON de los hilos |

**7. Canal WhatsApp y persistencia por usuario (ADR 0014 y 0015)**
| Variable | Por defecto | Para qué |
|---|---|---|
| `WHATSAPP_TOKEN` | (obligatoria) | Token de acceso de Meta (temporal de 24 h o permanente de un usuario del sistema) |
| `WHATSAPP_PHONE_NUMBER_ID` | (obligatoria) | Identificador del número emisor |
| `WHATSAPP_VERIFY_TOKEN` | (obligatoria) | Cadena inventada que se registra en Meta para verificar el webhook |
| `WHATSAPP_APP_SECRET` | (obligatoria) | App Secret: verifica la firma `X-Hub-Signature-256` de cada notificación |
| `USER_ID_HASH_SECRET` | (obligatoria) | Secreto del HMAC que seudonimiza los números; respaldarlo |
| `WHATSAPP_API_VERSION` | `v23.0` | Versión de la Graph API |
| `WHATSAPP_HOST` / `WHATSAPP_PORT` | `127.0.0.1` / `8001` | Escucha del webhook; solo loopback (ngrok publica la URL) |
| `WHATSAPP_SEND_TIMEOUT_SECONDS` | `15` | Espera máxima de cada envío a Meta |
| `WHATSAPP_WAIT_NOTICE_SECONDS` | `10` | Segundos antes del aviso "Estoy revisando tu mensaje" |
| `WHATSAPP_MAX_PENDING` | `100` | Mensajes en cola antes de pedir a Meta que reintente (503) |
| `DATABASE_PATH` | `data/cardio_materno.db` | Base SQLite de usuarios, hilos y eventos (no se versiona) |
| `THREAD_IDLE_TIMEOUT_HOURS` | `12` | Horas sin actividad tras las cuales se cierra el hilo abierto |
Al arrancar, la consola muestra el modelo de cada etapa y el umbral efectivo del RAG (`… · umbral 0.50`).

### Problemas frecuentes
| Mensaje | Solución |
|---|---|
| "No se pudo conectar con Ollama…" | `ollama serve` o `sudo systemctl start ollama`; revisa `OLLAMA_BASE_URL` |
| "El modelo '…' no está instalado…" | Ejecuta el `ollama pull …` que indica el mensaje |
| "Ollama tardó más de … s…" o turnos muy lentos | Ver el diagnóstico de latencia en [operacion.md](operacion.md) |
| "⚠️ RAG no disponible: … Índice … ausente" | `.venv/bin/python run_build_kb_index.py` |
| "… se construyó con '…' y OLLAMA_EMBED_MODEL es '…'" / "La base … cambió" | Reconstruye el índice |
| `error: externally-managed-environment` al usar pip | Usa el entorno virtual: `.venv/bin/pip …` |
| "Faltan variables en .env: WHATSAPP_…" | Completa la sección 9 de `.env` (ver "Canal WhatsApp") |
| Meta no verifica el webhook ("The callback URL or verify token couldn't be validated") | `run_whatsapp.py` y ngrok deben estar corriendo; la URL termina en `/webhooks/whatsapp`; el token es idéntico a `WHATSAPP_VERIFY_TOKEN` |
| Llega el mensaje (POST 200 en ngrok) pero no hay respuesta | Mira la terminal 1: `131030 … allowed list` = el número no está verificado en "To"; `190 … expired` = token vencido; `100 … Invalid parameter` = revisa `WHATSAPP_PHONE_NUMBER_ID` |
| POST con 401 en ngrok | `WHATSAPP_APP_SECRET` no coincide con el App Secret de la app |
| No llega ningún POST | Falta suscribirse al campo `messages` en Webhook fields, o la cuenta de WhatsApp Business no está suscrita a la app (paso 4b) |
| `Object with ID '<WABA_ID>' does not exist` (código 100, subcódigo 33) al suscribir | Se dejó el texto de ejemplo: reemplaza `<WABA_ID>` por el WhatsApp Business Account ID real (no el Phone number ID) |

## B. Desarrollo (Windows o Linux; no requiere Ollama)
```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
pytest                 # pruebas sin Ollama (excluye las "live")
ruff check .           # estilo, complejidad y docstrings
mypy src tests scripts # tipos (modo estricto)
```
