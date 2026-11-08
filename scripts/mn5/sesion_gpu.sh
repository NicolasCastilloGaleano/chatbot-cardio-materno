#!/usr/bin/env bash
# Corre en el nodo con GPU (lo lanza pedir_gpu.sh): arranca Ollama solo en 127.0.0.1 con un
# puerto libre, ejecuta las acciones pedidas y detiene Ollama al terminar.
#
# Acciones (en orden; por defecto, consola):
#   consola  chat por consola (construye el índice si no existe)
#   indice   reconstruye el índice de la base de conocimiento
#   pruebas  pytest sin Ollama (excluye las live)
#   live     pytest -m live -s (requiere Ollama)
#   shell    terminal en el nodo con Ollama ya arrancado; `exit` termina la sesión
# Guía: docs/08-despliegue/marenostrum5.md
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

PYTHON="$MN5_REPO/.venv/bin/python"
INDEX_DIR="$MN5_REPO/data/kb_index"

require_gpu_step() {
    # Solo tiene sentido dentro de un paso de SLURM con GPU.
    if [ -z "${SLURM_STEP_ID:-}" ]; then
        mn5_fail "Este script corre en el nodo con GPU. Desde glogin4 usa: bash scripts/mn5/pedir_gpu.sh"
    fi
    [ -x "$PYTHON" ] || mn5_fail "No existe .venv: ejecuta antes bash scripts/mn5/preparar.sh en glogin4."
    [ -x "$OLLAMA_BIN" ] || mn5_fail "Ollama no está instalado: ejecuta antes bash scripts/mn5/preparar.sh."
}

show_gpu() {
    # Muestra la GPU asignada y su memoria.
    echo "Nodo $(hostname) · job $SLURM_JOB_ID"
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv || true
}

build_index() {
    "$PYTHON" run_build_kb_index.py
}

run_console() {
    # Construye el índice si falta y abre la consola.
    [ -d "$INDEX_DIR" ] || build_index
    "$PYTHON" run_console.py
}

open_shell() {
    echo "Ollama corre en $OLLAMA_BASE_URL. Escribe 'exit' para terminar y liberar la GPU."
    bash -i
}

run_action() {
    # Ejecuta una acción. Args: $1 = nombre de la acción.
    case "$1" in
        consola) run_console ;;
        indice) build_index ;;
        pruebas) "$PYTHON" -m pytest ;;
        live) "$PYTHON" -m pytest -m live -s ;;
        shell) open_shell ;;
        *) echo "Acción desconocida: $1 (usa consola, indice, pruebas, live o shell)" >&2; return 1 ;;
    esac
}

main() {
    require_gpu_step
    mn5_load_python
    mkdir -p "$MN5_LOGS"
    show_gpu
    trap mn5_stop_ollama EXIT
    mn5_start_ollama "$MN5_LOGS/ollama-$SLURM_JOB_ID.log"
    cd "$MN5_REPO"
    [ $# -eq 0 ] && set -- consola
    local action
    for action in "$@"; do
        echo "== $action"
        run_action "$action" || echo "La acción '$action' terminó con error; sigue la siguiente." >&2
    done
}

main "$@"
