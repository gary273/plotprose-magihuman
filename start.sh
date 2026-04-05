#!/bin/bash
# PlotProse MagiHuman — Production Entrypoint
# NEVER exits on error. Starts Flask immediately.
# Detects mode: serverless vs pod-http.

# Do NOT use set -e — container must never crash
set +e

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"; }

log "=========================================="
log "PlotProse MagiHuman Worker"
log "Mode: ${RUNPOD_SERVERLESS:+serverless}${RUNPOD_SERVERLESS:-pod-http}"
log "=========================================="

# --- Diagnostics ---
log "Python: $(python3 --version 2>&1)"
log "Disk (root): $(df -h / | tail -1 | awk '{print $4 " free of " $2}')"
log "Disk (volume): $(df -h /runpod-volume 2>/dev/null | tail -1 | awk '{print $4 " free of " $2}' || echo 'NOT MOUNTED')"
log "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'not detected')"
log "RAM: $(free -h | awk '/^Mem:/{print $7 " free of " $2}')"

# --- Safety net: install missing critical packages ---
# --ignore-installed needed because base image has distutils blinker 1.4
# that blocks Flask install (Flask needs blinker>=1.9)
log "Checking critical packages..."
python3 -c "import flask" 2>/dev/null || {
    log "Flask missing — installing (with --ignore-installed for blinker)..."
    pip install --no-cache-dir --ignore-installed blinker flask 2>&1 | tail -5
}
python3 -c "import runpod" 2>/dev/null || {
    log "runpod missing — installing..."
    pip install --no-cache-dir runpod 2>&1 | tail -5
}
python3 -c "import huggingface_hub" 2>/dev/null || {
    log "huggingface_hub missing — installing..."
    pip install --no-cache-dir huggingface_hub 2>&1 | tail -5
}
log "Critical packages OK"

# --- Ensure directories ---
mkdir -p /runpod-volume/models 2>/dev/null || true
mkdir -p /workspace/models 2>/dev/null || true
mkdir -p /workspace/output 2>/dev/null || true

# --- Set unbuffered Python ---
export PYTHONUNBUFFERED=1

# --- Signal handling ---
trap 'log "Shutting down..."; exit 0' SIGTERM SIGINT

# --- Start ---
if [ "${RUNPOD_SERVERLESS}" = "1" ]; then
    log "Starting RunPod serverless handler..."
    exec python3 -u /workspace/handler.py
else
    log "Starting HTTP server on port ${PORT:-8000}..."
    log "Health endpoint available immediately at /health"
    # Use exec so signals go directly to Python
    exec python3 -u /workspace/pod_server.py
fi
