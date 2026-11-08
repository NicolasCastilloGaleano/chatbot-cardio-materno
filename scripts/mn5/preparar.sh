#!/usr/bin/env bash
# Prepara el proyecto en MareNostrum 5 desde el nodo de acceso (glogin4), el único con internet.
# Instala el entorno de Python, Ollama en el espacio del proyecto, los modelos y el .env.
# Se puede repetir: cada paso se salta si ya está hecho.
#
# Uso:   bash scripts/mn5/preparar.sh
# Sin internet en glogin4: MN5_OLLAMA_ARCHIVE=/ruta/ollama-linux-amd64.tgz bash scripts/mn5/preparar.sh
# Guía:  docs/08-despliegue/marenostrum5.md
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

OLLAMA_URL_BASE="https://ollama.com/download/ollama-linux-amd64"

require_login_node() {
    # Este script descarga; en los nodos de GPU no hay internet.
    if [ -n "${SLURM_JOB_ID:-}" ]; then
        mn5_fail "Ejecútalo en glogin4, fuera de una asignación de SLURM (ahora estás en el job $SLURM_JOB_ID)."
    fi
}

write_conf() {
    # Crea mn5.conf con los valores por defecto, fuera del repositorio.
    [ -f "$MN5_CONF" ] && return 0
    cat >"$MN5_CONF" <<'CONF'
# Configuración local de los scripts de MN5 (fuera del repositorio; no se versiona).
# Módulos para tener Python 3.12 o superior, en orden y separados por espacios. Elige uno de
# `module avail python`; si Lmod pide otros antes (p. ej., hdf5), van primero:
#   MN5_PYTHON_MODULE="hdf5 python/3.12.1"
# Vacío = usa el python3 del sistema.
MN5_PYTHON_MODULE=""
# Recursos de las sesiones con GPU (confirma las colas con `bsc_queues`).
MN5_QOS="acc_debug"
MN5_TIME="02:00:00"
MN5_CPUS="20"
CONF
    echo "Creado $MN5_CONF (revisa MN5_PYTHON_MODULE)."
}

setup_venv() {
    # Crea .venv con el Python del módulo e instala las dependencias.
    mn5_load_python
    mn5_check_python
    if [ ! -x "$MN5_REPO/.venv/bin/python" ]; then
        python3 -m venv "$MN5_REPO/.venv"
    fi
    check_venv_isolated
    "$MN5_REPO/.venv/bin/pip" install --upgrade pip
    "$MN5_REPO/.venv/bin/pip" install -r "$MN5_REPO/requirements.txt" -r "$MN5_REPO/requirements-dev.txt"
}

check_venv_isolated() {
    # Verifica que .venv sea un entorno propio y no el Python del módulo (p. ej., por PYTHONHOME).
    if ! "$MN5_REPO/.venv/bin/python" -c "import sys; sys.exit(sys.prefix == sys.base_prefix)"; then
        mn5_fail ".venv no quedó aislado del Python del módulo. Bórralo (rm -rf .venv) y pega aquí la salida de:
  module show ${MN5_PYTHON_MODULE##* }"
    fi
}

download_ollama() {
    # Descarga el paquete de Ollama para Linux (.tgz o, en versiones nuevas, .tar.zst). Args: $1 = destino.
    if curl -fL --retry 3 -o "$1.tgz" "$OLLAMA_URL_BASE.tgz"; then
        echo "$1.tgz"
    elif curl -fL --retry 3 -o "$1.tar.zst" "$OLLAMA_URL_BASE.tar.zst"; then
        echo "$1.tar.zst"
    else
        mn5_fail "No se pudo descargar Ollama. Súbelo desde tu PC por transfer1 y usa MN5_OLLAMA_ARCHIVE."
    fi
}

extract_ollama() {
    # Descomprime el paquete de Ollama en $OLLAMA_DIR. Args: $1 = archivo.
    mkdir -p "$OLLAMA_DIR"
    case "$1" in
        *.tgz | *.tar.gz) tar -xzf "$1" -C "$OLLAMA_DIR" ;;
        *.tar.zst) tar --use-compress-program=unzstd -xf "$1" -C "$OLLAMA_DIR" ;;
        *) mn5_fail "Formato no reconocido: $1" ;;
    esac
}

install_ollama() {
    # Instala Ollama en el espacio del proyecto (sin sudo), si no está.
    if [ -x "$OLLAMA_BIN" ]; then
        echo "Ollama ya está instalado: $("$OLLAMA_BIN" --version 2>&1 | tail -n 1)"
        return 0
    fi
    local archive="${MN5_OLLAMA_ARCHIVE:-}"
    if [ -z "$archive" ]; then
        archive="$(download_ollama "$MN5_WORK/ollama-download")"
    fi
    extract_ollama "$archive"
    [ -z "${MN5_OLLAMA_ARCHIVE:-}" ] && rm -f "$archive"
    "$OLLAMA_BIN" --version
}

pull_models() {
    # Descarga los modelos con un servidor temporal que no usa GPU (solo descarga, no ejecuta).
    mkdir -p "$OLLAMA_MODELS" "$MN5_LOGS"
    trap mn5_stop_ollama EXIT
    CUDA_VISIBLE_DEVICES="" mn5_start_ollama "$MN5_LOGS/ollama-preparar.log"
    local model
    for model in "${MN5_MODELS[@]}"; do
        "$OLLAMA_BIN" pull "$model"
    done
    "$OLLAMA_BIN" create "$MN5_CPU_MODEL" -f "$MN5_CPU_MODELFILE"
    "$OLLAMA_BIN" list
    mn5_stop_ollama
    trap - EXIT
}

create_env() {
    # Crea .env desde .env.example. OLLAMA_BASE_URL lo fija sesion_gpu.sh en cada sesión.
    if [ -f "$MN5_REPO/.env" ]; then
        echo ".env ya existe: no se modifica."
        return 0
    fi
    cp "$MN5_REPO/.env.example" "$MN5_REPO/.env"
    echo "Creado .env desde .env.example (sin secretos de WhatsApp: en MN5 no se usa ese canal)."
}

main() {
    require_login_node
    mkdir -p "$MN5_LOGS"
    write_conf
    # shellcheck source=/dev/null
    source "$MN5_CONF"
    echo "== 1/4 Entorno de Python" && setup_venv
    echo "== 2/4 Ollama" && install_ollama
    echo "== 3/4 Modelos (unos 25 GB)" && pull_models
    echo "== 4/4 .env" && create_env
    echo "Listo. Para usar la GPU: bash scripts/mn5/pedir_gpu.sh consola"
}

main "$@"
