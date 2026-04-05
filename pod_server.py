#!/usr/bin/env python3
"""
PlotProse MagiHuman - Production HTTP Server (Regular GPU Pod)
Starts Flask IMMEDIATELY, downloads models in background thread.
Never blocks startup on model downloads.

Endpoints:
    GET  /health        - Health check with download progress
    GET  /ready         - Simple boolean for load balancers
    POST /runsync       - Synchronous generation (blocks until result)
    POST /generate      - Async generation (returns job ID)
    POST /run           - Alias for /generate
    GET  /status/<id>   - Check async job status
    POST /retry-download - Retry failed model download
"""

import os
import sys
import json
import uuid
import threading
import time
import traceback
import logging
from datetime import datetime

from flask import Flask, request, jsonify

try:
    from handler import handler as serverless_handler, ensure_models
except ImportError as e:
    print(f"WARNING: Could not import handler module: {e}", flush=True)
    serverless_handler = None
    ensure_models = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger("magihuman")

app = Flask(__name__)
jobs = {}
models_ready = False
download_status = {
    "state": "pending",
    "message": "",
    "started_at": None,
    "completed_at": None,
    "retry_count": 0,
    "error": None,
}
download_lock = threading.Lock()


def set_download_state(state, message="", error=None):
    global models_ready
    with download_lock:
        download_status["state"] = state
        download_status["message"] = message
        download_status["error"] = error
        if state == "downloading" and download_status["started_at"] is None:
            download_status["started_at"] = time.time()
        if state == "ready":
            models_ready = True
            download_status["completed_at"] = time.time()
        if state == "error":
            models_ready = False


def download_models_background(max_retries=3):
    global models_ready
    for attempt in range(1, max_retries + 1):
        try:
            set_download_state("downloading", f"Attempt {attempt}/{max_retries}")
            log.info(f"Model download attempt {attempt}/{max_retries}")
            if ensure_models is None:
                raise RuntimeError("ensure_models not available (handler import failed)")
            result = ensure_models()
            if result:
                set_download_state("ready", "All models downloaded and verified")
                log.info("Models ready - server fully operational")
                return
            else:
                raise RuntimeError("ensure_models returned False")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            log.error(f"Download attempt {attempt} failed: {error_msg}")
            with download_lock:
                download_status["retry_count"] = attempt
            if attempt < max_retries:
                wait = min(60, 10 * (2 ** (attempt - 1)))
                log.info(f"Retrying in {wait}s...")
                set_download_state("downloading", f"Retry {attempt} in {wait}s after: {error_msg}")
                time.sleep(wait)
            else:
                set_download_state("error", f"Failed after {max_retries} attempts", error_msg)
                log.error(f"Model download permanently failed: {error_msg}")


@app.route("/health", methods=["GET"])
def health():
    with download_lock:
        state = download_status["state"]
        elapsed = None
        if download_status["started_at"]:
            elapsed = int(time.time() - download_status["started_at"])
    response = {
        "status": "healthy" if models_ready else state,
        "models_ready": models_ready,
        "mode": "pod-http",
        "jobs_pending": sum(1 for j in jobs.values() if j["status"] == "IN_PROGRESS"),
        "jobs_completed": sum(1 for j in jobs.values() if j["status"] == "COMPLETED"),
    }
    if not models_ready:
        response["download"] = {
            "state": state,
            "message": download_status.get("message", ""),
            "elapsed_seconds": elapsed,
            "retry_count": download_status.get("retry_count", 0),
        }
        if download_status.get("error"):
            response["download"]["error"] = download_status["error"]
    return jsonify(response), 200


@app.route("/ready", methods=["GET"])
def ready():
    if models_ready:
        return jsonify({"ready": True}), 200
    return jsonify({"ready": False}), 503


@app.route("/retry-download", methods=["POST"])
def retry_download():
    with download_lock:
        state = download_status["state"]
    if state != "error":
        return jsonify({"error": f"Cannot retry - current state is '{state}'"}), 400
    log.info("Manual download retry requested")
    set_download_state("pending", "Manual retry initiated")
    thread = threading.Thread(target=download_models_background, daemon=True)
    thread.start()
    return jsonify({"message": "Download retry started"}), 202


@app.route("/runsync", methods=["POST"])
def runsync():
    data = request.get_json()
    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in request body"}), 400
    if not models_ready:
        return jsonify({"error": "Models still initializing", "download_state": download_status["state"], "retry_after": 30}), 503
    if serverless_handler is None:
        return jsonify({"error": "Handler not available"}), 500
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "input": data["input"]}
    try:
        result = serverless_handler(job)
        return jsonify({"id": job_id, "status": "COMPLETED", "output": result})
    except Exception as e:
        log.error(f"runsync error: {e}")
        return jsonify({"id": job_id, "status": "FAILED", "error": str(e)}), 500


@app.route("/generate", methods=["POST"])
@app.route("/run", methods=["POST"])
def generate_async():
    data = request.get_json()
    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in request body"}), 400
    if not models_ready:
        return jsonify({"error": "Models still initializing", "download_state": download_status["state"], "retry_after": 30}), 503
    if serverless_handler is None:
        return jsonify({"error": "Handler not available"}), 500
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "IN_PROGRESS", "output": None, "error": None}
    def run_job():
        try:
            job = {"id": job_id, "input": data["input"]}
            result = serverless_handler(job)
            jobs[job_id] = {"status": "COMPLETED", "output": result, "error": None}
        except Exception as e:
            log.error(f"Async job {job_id} failed: {e}")
            jobs[job_id] = {"status": "FAILED", "output": None, "error": str(e)}
    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()
    return jsonify({"id": job_id, "status": "IN_QUEUE"})


@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    job = jobs[job_id]
    response = {"id": job_id, "status": job["status"]}
    if job["output"]: response["output"] = job["output"]
    if job["error"]: response["error"] = job["error"]
    return jsonify(response)


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("PlotProse MagiHuman Pod Server - Production Mode")
    log.info("=" * 60)
    log.info(f"Python {sys.version}")
    download_thread = threading.Thread(target=download_models_background, daemon=True)
    download_thread.start()
    log.info("Background model download started")
    port = int(os.environ.get("PORT", "8000"))
    log.info(f"Flask starting on 0.0.0.0:{port}")
    log.info("Health endpoint available immediately at /health")
    log.info("=" * 60)
    app.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)
