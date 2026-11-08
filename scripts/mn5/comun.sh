# shellcheck shell=bash
# Variables y funciones comunes de los scripts de MareNostrum 5 (MN5).
# Se carga con `source` desde los demás scripts; no se ejecuta solo.
# Guía: docs/08-despliegue/marenostrum5.md

# --- Rutas: el repositorio está en <MN5_WORK>/chatbot-cardio-materno ---
MN5_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MN5_WORK="${MN5_WORK:-$(dirname "$MN5_REPO")}"
MN5_CONF="$MN5_WORK/mn5.conf"
MN5_LOGS="$MN5_WORK/logs"
OLLAMA_DIR="$MN5_WORK/ollama"
OLLAMA_BIN="$OLLAMA_DIR/bin/ollama"
export OLLAMA_MODELS="$OLLAMA_DIR/models"

# Configuración local (no se versiona): la crea preparar.sh la primera vez.
if [ -f "$MN5_CONF" ]; then
    # shellcheck source=/dev/null
    source "$MN5_CONF"
fi

# --- Recursos de SLURM (se pueden cambiar en mn5.conf; ver `bsc_queues`) ---
MN5_ACCOUNT="${MN5_ACCOUNT:-bsc08}"
MN5_PARTITION="${MN5_PARTITION:-acc}"
MN5_QOS="${MN5_QOS:-acc_debug}"
MN5_TIME="${MN5_TIME:-02:00:00}"
MN5_CPUS="${MN5_CPUS:-20}"
MN5_PYTHON_MODULE="${MN5_PYTHON_MODULE:-}"

# Modelos del proyecto (ADR 0011) y la copia en CPU de la etapa de respuesta.
MN5_MODELS=(mistral-small3.1:24b qwen3:8b qwen3-embedding:8b)
MN5_CPU_MODEL="qwen3-cpu"
MN5_CPU_MODELFILE="$MN5_REPO/docs/08-despliegue/qwen3-cpu.Modelfile"

# Puertos: el nodo de acceso y los nodos de GPU son compartidos, así que no se usa el 11434.
MN5_PORT_BASE=20000
MN5_PORT_RANGE=20000
MN5_OLLAMA_WAIT_TRIES=60
MN5_OLLAMA_WAIT_SECONDS=2
MN5_OLLAMA_START_ATTEMPTS=3
MN5_MIN_PYTHON="3.12"

# El espacio de GPFS es compartido por el equipo: archivos solo para el dueño y el grupo.
umask 007

mn5_fail() {
    # Muestra un error en español y termina el script.
    echo "ERROR: $*" >&2
    exit 1
}

mn5_load_python() {
    # Carga los módulos de mn5.conf, en orden y separados por espacios (p. ej., "hdf5 python/3.12.1").
    # Lmod no tolera `set -u`. El módulo de Python define PYTHONPATH con sus propios paquetes; se
    # quita para que .venv use solo los que instala requirements.txt.
    [ -z "$MN5_PYTHON_MODULE" ] && return 0
    set +u
    if ! type module >/dev/null 2>&1; then
        # shellcheck source=/dev/null
        source /etc/profile >/dev/null 2>&1 || true
    fi
    # shellcheck disable=SC2086 # la lista de módulos se separa a propósito
    module load $MN5_PYTHON_MODULE || mn5_fail "No se pudieron cargar los módulos '$MN5_PYTHON_MODULE'.
Revisa los que exige con \`module spider <módulo>\` y agrégalos antes, en MN5_PYTHON_MODULE ($MN5_CONF)."
    set -u
    unset PYTHONPATH
}

mn5_check_python() {
    # Verifica que python3 sea 3.12 o superior.
    command -v python3 >/dev/null 2>&1 || mn5_fail "No hay python3. Define MN5_PYTHON_MODULE en $MN5_CONF."
    if ! python3 -c "import sys; sys.exit(sys.version_info < (3, 12))"; then
        mn5_fail "python3 es $(python3 --version 2>&1) y el proyecto pide $MN5_MIN_PYTHON o superior.
Busca uno con \`module avail python\` y escríbelo en MN5_PYTHON_MODULE ($MN5_CONF)."
    fi
}

mn5_random_port() {
    # Elige un puerto al azar para no chocar con otros usuarios del mismo nodo.
    echo $((MN5_PORT_BASE + RANDOM % MN5_PORT_RANGE))
}

mn5_wait_ollama() {
    # Espera a que el servidor de Ollama responda; falla si el proceso muere.
    local tries
    for ((tries = 0; tries < MN5_OLLAMA_WAIT_TRIES; tries++)); do
        kill -0 "$MN5_OLLAMA_PID" 2>/dev/null || return 1
        "$OLLAMA_BIN" list >/dev/null 2>&1 && return 0
        sleep "$MN5_OLLAMA_WAIT_SECONDS"
    done
    return 1
}

mn5_start_ollama() {
    # Arranca `ollama serve` en 127.0.0.1 con un puerto libre. Args: $1 = archivo de log.
    local attempt
    for ((attempt = 1; attempt <= MN5_OLLAMA_START_ATTEMPTS; attempt++)); do
        export OLLAMA_HOST="127.0.0.1:$(mn5_random_port)"
        "$OLLAMA_BIN" serve >>"$1" 2>&1 &
        MN5_OLLAMA_PID=$!
        if mn5_wait_ollama; then
            export OLLAMA_BASE_URL="http://$OLLAMA_HOST"
            echo "Ollama listo en $OLLAMA_HOST (log: $1)"
            return 0
        fi
        mn5_stop_ollama
    done
    mn5_fail "Ollama no arrancó tras $MN5_OLLAMA_START_ATTEMPTS intentos; revisa $1"
}

mn5_stop_ollama() {
    # Detiene el servidor de Ollama que arrancó este script, si sigue vivo.
    if [ -n "${MN5_OLLAMA_PID:-}" ] && kill -0 "$MN5_OLLAMA_PID" 2>/dev/null; then
        kill "$MN5_OLLAMA_PID" 2>/dev/null || true
        wait "$MN5_OLLAMA_PID" 2>/dev/null || true
    fi
    MN5_OLLAMA_PID=""
    return 0
}
