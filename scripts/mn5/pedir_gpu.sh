#!/usr/bin/env bash
# Abre una sesión en un nodo con GPU H100 y ejecuta sesion_gpu.sh, con terminal interactiva.
# - Sin reserva: pide 1 GPU a SLURM; al terminar, la GPU se libera sola.
# - Dentro de una reserva de `salloc`: entra en ella sin volver a la cola; la reserva sigue
#   activa hasta `scancel $SLURM_JOB_ID` o hasta que se acaba su tiempo.
#
# Uso (en glogin4):
#   bash scripts/mn5/pedir_gpu.sh                 # consola del chat
#   bash scripts/mn5/pedir_gpu.sh indice live     # varias acciones seguidas (ver sesion_gpu.sh)
# Guía: docs/08-despliegue/marenostrum5.md
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

SESSION_SCRIPT="$MN5_REPO/scripts/mn5/sesion_gpu.sh"

if [ -n "${SLURM_STEP_ID:-}" ]; then
    # Ya es una terminal en el nodo con GPU (dentro de un paso de SLURM).
    exec bash "$SESSION_SCRIPT" "$@"
fi

if [ -n "${SLURM_JOB_ID:-}" ]; then
    echo "Usando la reserva activa (job $SLURM_JOB_ID), sin volver a la cola."
    echo "Al terminar del todo, libérala con: scancel $SLURM_JOB_ID"
    exec srun --jobid="$SLURM_JOB_ID" --pty bash "$SESSION_SCRIPT" "$@"
fi

echo "Pidiendo 1 GPU: cuenta $MN5_ACCOUNT, cola $MN5_QOS, $MN5_CPUS CPU, máximo $MN5_TIME…"
echo "(Puede tardar si la cola está llena. Ctrl+C cancela la solicitud.)"
exec srun --account="$MN5_ACCOUNT" --partition="$MN5_PARTITION" --qos="$MN5_QOS" \
    --nodes=1 --ntasks=1 --gres=gpu:1 --cpus-per-task="$MN5_CPUS" --time="$MN5_TIME" \
    --job-name=cardio-materno --pty \
    bash "$SESSION_SCRIPT" "$@"
