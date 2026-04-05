#!/bin/bash
# PlotProse MagiHuman - Production Entrypoint
# NEVER exits on error. Starts Flask immediately.
set +e

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

log "=========================================="
log "PlotProse MagiHuman Worker"
log "Mode: ${RUNPOD_SERVERLESS:+serverless}${RUNPOD_SERVERLESS:-pod-http}"
log "=========================================="

log "Python: $(python3 --version 2>&1)"
log "Disk (root): $(df -h / | tail -1 | awk '{print $4 " free of " $2}')"
log "Disk (volume): $(df -h /runpod-volume 2>/dev/null | tail -1 | awk '{print $4 " free of " $2}' || echo 'NOT MOUNTED')"
log "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'not detected')"
log "RAM: $(free -h | awk '/^Mem:/{print $7 " free of " $2}')"

mkdir -p /runpod-volume/models 2>/dev/null || true
mkdir -p /workspace/models 2>/dev/null || true
mkdir -p /workspace/output 2>/dev/null || true

export PYTHONUNBUFFERED=1
trap 'log "Shutting down..."; exit 0' SIGTERM SIGINT

if [ "${RUNPOD_SERVERLESS}" = "1" ]; then
    log "Starting RunPod serverless handler..."
    exec python3 -u /workspace/handler.py
else
    log "Starting HTTP server on port ${PORT:-8000}..."
    log "Health endpoint available immediately at /health"
    exec python3 -u /workspace/pod_server.py
fi
