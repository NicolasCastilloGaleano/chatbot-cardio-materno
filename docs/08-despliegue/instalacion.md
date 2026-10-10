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

**Evidencia (HU-02):**
1. `¿por qué es importante controlar la presión si no me duele nada?` → respuesta basada en la base, con `[evidencia … citadas: E…]`
2. `¿qué puedo comer si tengo acidez en el embarazo?` → evidencia de la categoría materna correspondiente
3. Una pregunta fuera de la base (p. ej., `¿qué opinas del fútbol?`) → el asistente dice que no tiene información validada; evidencia `insuficiente`
4. Anota los `[tiempos …]`: sirven para decidir si conviene un modelo más pequeño en el análisis (`OLLAMA_ANALYSIS_MODEL`)

**Pruebas en vivo (sonda de recuperación y no contaminación):**
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

### Problemas frecuentes
| Mensaje | Solución |
|---|---|
| "No se pudo conectar con Ollama…" | `ollama serve` o `sudo systemctl start ollama`; revisa `OLLAMA_BASE_URL` |
| "El modelo '…' no está instalado…" | Ejecuta el `ollama pull …` que indica el mensaje |
| "Ollama tardó más de … s…" | Sube `OLLAMA_TIMEOUT_SECONDS` o usa un modelo más pequeño en `OLLAMA_ANALYSIS_MODEL` |
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
