#!/bin/bash
# PlotProse MagiHuman — Entrypoint Script
# Detects mode and starts the appropriate server:
#   RUNPOD_SERVERLESS=1 → RunPod serverless handler (uses job queue)
#   Otherwise           → HTTP server on port 8000 (regular GPU pod)

set -e

echo "=========================================="
echo "PlotProse MagiHuman Worker"
echo "Mode: ${RUNPOD_SERVERLESS:+serverless}${RUNPOD_SERVERLESS:-pod-http}"
echo "=========================================="

if [ "${RUNPOD_SERVERLESS}" = "1" ]; then
    echo "Starting RunPod serverless handler..."
    exec python -u /workspace/handler.py
else
    echo "Starting HTTP server on port ${PORT:-8000}..."
    exec python -u /workspace/pod_server.py
fi
