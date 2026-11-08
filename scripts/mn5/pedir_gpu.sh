#!/usr/bin/env bash
# Pide una GPU H100 a SLURM y ejecuta sesion_gpu.sh en ese nodo, con terminal interactiva.
# Al terminar (o al salir de la consola), la GPU se libera sola.
#
# Uso (en glogin4):
#   bash scripts/mn5/pedir_gpu.sh                 # consola del chat
#   bash scripts/mn5/pedir_gpu.sh indice live     # varias acciones seguidas (ver sesion_gpu.sh)
# Guía: docs/08-despliegue/marenostrum5.md
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

if [ -n "${SLURM_JOB_ID:-}" ]; then
    mn5_fail "Ya estás dentro del job $SLURM_JOB_ID: usa directamente bash scripts/mn5/sesion_gpu.sh"
fi

echo "Pidiendo 1 GPU: cuenta $MN5_ACCOUNT, cola $MN5_QOS, $MN5_CPUS CPU, máximo $MN5_TIME…"
echo "(Puede tardar si la cola está llena. Ctrl+C cancela la solicitud.)"
exec srun --account="$MN5_ACCOUNT" --partition="$MN5_PARTITION" --qos="$MN5_QOS" \
    --nodes=1 --ntasks=1 --gres=gpu:1 --cpus-per-task="$MN5_CPUS" --time="$MN5_TIME" \
    --job-name=cardio-materno --pty \
    bash "$MN5_REPO/scripts/mn5/sesion_gpu.sh" "$@"
