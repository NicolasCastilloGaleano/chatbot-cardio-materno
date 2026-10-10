# Instalación y ejecución

*Última actualización: 2026-10-10*

## A. PC de pruebas: ejecutar el chat por consola con Ollama (HU-00)
Requisitos: **Python 3.12+**, **Git** y **[Ollama](https://ollama.com/download)**. El chat **no necesita `pip install`**: solo usa la librería estándar.

```powershell
# 1. Primera vez: clonar
git clone https://github.com/NicolasCastilloGaleano/chatbot-cardio-materno.git
cd chatbot-cardio-materno

# 1b. Las siguientes veces: traer los últimos cambios (y la rama a probar)
git pull

# 2. Descargar el modelo (una sola vez, ~15 GB)
ollama pull mistral-small3.1:24b

# 3. Crear la configuración local (una sola vez) y ajustarla si hace falta
copy .env.example .env

# 4. Ejecutar el chat
python run_console.py
```
Escribe tus mensajes y presiona Enter. Para terminar, escribe `salir` (o usa Ctrl+C). Cada consulta queda en un hilo, guardado en `data/threads/<id>.json`.

**Guion de prueba de la HU-06:**
1. `Estoy embarazada de 5 meses y tengo mucha acidez` → `[hilo … | materno_infantil | abierto | nuevo]`
2. `¿Qué puedo comer para eso?` → mismo hilo, `continúa`
3. `Otra cosa, mi papá tiene la presión alta` → otro hilo, `cardiovascular | nuevo`
4. `salir` → revisa `data/threads/`: los dos hilos deben quedar `cerrado`

**Guion de prueba de alarmas (HU-03/HU-04):**
1. `estoy embarazada y tengo un sangrado` → solo el mensaje fijo 🚨 y `⚠️ RN-MI-01 urgencia_inmediata (usuario)` (el modelo no se consulta, así que la respuesta es inmediata)
2. `mi papá tiene la presión alta` → mensaje fijo ⚠️ + la orientación del agente, y `RN-CV-06 consulta_prioritaria`
3. Una frase coloquial que las reglas no captan, p. ej. `me está saliendo como agüita rosada por abajo, tengo 7 meses` → si el agente reporta el síntoma, verás la alerta con origen `(agente)`
4. Una conversación normal (p. ej., `¿qué puedo comer para la acidez?`) → sin alertas
5. En `data/threads/<id>.json`, la lista `alerts` registra cada alerta

| Variable (`.env`) | Por defecto | Para qué |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Dirección del servidor Ollama |
| `OLLAMA_MODEL` | `mistral-small3.1:24b` | Modelo (nombre exacto de `ollama list`) |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Espera máxima por respuesta |
| `OLLAMA_TEMPERATURE` | `0.3` | Creatividad de las respuestas (0 = más predecible) |
| `OLLAMA_NUM_CTX` | `4096` | Ventana de contexto en tokens |
| `THREAD_CONTEXT_MESSAGES` | `6` | Mensajes recientes del hilo que se envían al agente |
| `SHOW_THREAD_DEBUG` | `true` | Muestra la línea de estado del hilo después de cada respuesta |
| `THREADS_DIR` | `data/threads` | Carpeta donde se guardan los JSON de los hilos |
| `ALARM_RULES_FILE` | `knowledge/alarm_rules.json` | Catálogo de reglas de alarma (se valida al arrancar) |

### Problemas frecuentes
| Mensaje | Solución |
|---|---|
| "No se pudo conectar con Ollama…" | Abre la app de Ollama o ejecuta `ollama serve`; revisa `OLLAMA_BASE_URL` |
| "El modelo '…' no está instalado…" | Ejecuta el `ollama pull …` que indica el mensaje, o cambia `OLLAMA_MODEL` |
| "Ollama tardó más de … s…" | El modelo es pesado para el equipo: sube `OLLAMA_TIMEOUT_SECONDS` o usa un modelo más pequeño |

## B. Desarrollo: ejecutar pruebas y calidad (no requiere Ollama)
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest            # pruebas unitarias (usan dobles; no llaman a Ollama)
ruff check .      # estilo, complejidad y docstrings
mypy src tests    # tipos (modo estricto)
```
