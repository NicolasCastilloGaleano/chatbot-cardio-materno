# Instalación y ejecución

*Última actualización: 2026-10-10 (HU-02: RAG)*

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
```

### Las siguientes veces
```bash
git pull
.venv/bin/pip install -r requirements.txt     # por si cambiaron las dependencias
.venv/bin/python run_build_kb_index.py        # solo si cambió knowledge/kb/entries.jsonl o OLLAMA_EMBED_MODEL
.venv/bin/python run_console.py
```
Al arrancar se muestran las reglas de alarma cargadas, los modelos de cada etapa y el estado de la base de conocimiento. Si el índice no existe o no corresponde, aparece `⚠️ RAG no disponible…` con la instrucción para reconstruirlo; el chat sigue, pero sin información de salud.

Escribe tus mensajes y presiona Enter. Para terminar, escribe `salir` (o usa Ctrl+C). Cada consulta queda en un hilo, guardado en `data/threads/<id>.json`.

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
| Variable | Por defecto | Para qué |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Dirección del servidor Ollama |
| `OLLAMA_MODEL` | `mistral-small3.1:24b` | Modelo por defecto de ambas llamadas |
| `OLLAMA_ANALYSIS_MODEL` | (vacío = `OLLAMA_MODEL`) | Modelo de la llamada de análisis |
| `OLLAMA_REPLY_MODEL` | (vacío = `OLLAMA_MODEL`) | Modelo de la llamada de respuesta |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Espera máxima por respuesta |
| `OLLAMA_TEMPERATURE` | `0.3` | Creatividad (0 = más predecible) |
| `OLLAMA_NUM_CTX` | `4096` | Ventana de contexto en tokens |
| `THREAD_CONTEXT_MESSAGES` | `6` | Mensajes recientes del hilo que se envían al agente |
| `SHOW_THREAD_DEBUG` | `true` | Muestra las líneas de depuración |
| `THREADS_DIR` | `data/threads` | Carpeta de los JSON de los hilos |
| `ALARM_RULES_FILE` | `knowledge/alarm_rules.json` | Catálogo de reglas de alarma |
| `RAG_ENABLED` | `true` | Activa la búsqueda de evidencia |
| `OLLAMA_EMBED_MODEL` | `qwen3-embedding:8b` | Modelo de embeddings (debe coincidir con el del índice) |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `120` | Espera máxima por embedding |
| `EMBED_BATCH_SIZE` | `16` | Textos por lote al construir el índice |
| `KB_ENTRIES_FILE` | `knowledge/kb/entries.jsonl` | Base de conocimiento |
| `KB_INDEX_DIR` | `data/kb_index` | Índice vectorial (derivado) |
| `EVIDENCE_POLICY_FILE` | `knowledge/evidence_policy.json` | Umbral, top-k e instrucción de consulta |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tiempo que Ollama mantiene cargados los modelos entre turnos |
| `OLLAMA_EMBED_NUM_GPU` | `0` | Capas del embedder en GPU: `0` = CPU (deja la GPU al LLM), `auto` = decide Ollama (ver [operacion.md](operacion.md)) |
| `OLLAMA_ANALYSIS_NUM_PREDICT` | `600` | Máximo de tokens de la llamada de análisis (`auto` = sin límite) |
| `OLLAMA_REPLY_NUM_PREDICT` | `500` | Máximo de tokens de la llamada de respuesta (`auto` = sin límite) |
| `OLLAMA_THINK` | (vacío = no se envía) | `false` desactiva el razonamiento de modelos como qwen3 |
| `OLLAMA_ANALYSIS_THINK` / `OLLAMA_REPLY_THINK` | (vacío = `OLLAMA_THINK`) | Lo mismo, pero solo para una etapa (p. ej., qwen3 en el análisis y mistral en la respuesta) |

### Problemas frecuentes
| Mensaje | Solución |
|---|---|
| "No se pudo conectar con Ollama…" | `ollama serve` o `sudo systemctl start ollama`; revisa `OLLAMA_BASE_URL` |
| "El modelo '…' no está instalado…" | Ejecuta el `ollama pull …` que indica el mensaje |
| "Ollama tardó más de … s…" o turnos muy lentos | Ver el diagnóstico de latencia en [operacion.md](operacion.md) |
| "⚠️ RAG no disponible: … Índice … ausente" | `.venv/bin/python run_build_kb_index.py` |
| "… se construyó con '…' y OLLAMA_EMBED_MODEL es '…'" / "La base … cambió" | Reconstruye el índice |
| `error: externally-managed-environment` al usar pip | Usa el entorno virtual: `.venv/bin/pip …` |

## B. Desarrollo (Windows o Linux; no requiere Ollama)
```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
pytest                 # pruebas sin Ollama (excluye las "live")
ruff check .           # estilo, complejidad y docstrings
mypy src tests scripts # tipos (modo estricto)
```
