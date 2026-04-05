#!/usr/bin/env python3
"""
PlotProse MagiHuman — HTTP Server Mode (Regular GPU Pod)
Exposes the same avatar generation handler via a simple HTTP API.
Used when RunPod serverless is unavailable; deployed as a regular GPU pod.

Endpoints:
    POST /generate  — Submit an avatar generation job
    GET  /health    — Health check
    POST /runsync   — Synchronous generation (waits for result)

Request format (same as serverless):
{
    "input": {
        "prompt": "Your ad copy text here",
        "image_url": "https://url-to-brand-face.png",
        "resolution": "540p",
        "duration": 5
    }
}
"""

import os
import sys
import json
import uuid
import threading
import time
from flask import Flask, request, jsonify

# Import the handler function from our serverless handler
from handler import handler as serverless_handler, ensure_models

app = Flask(__name__)

# Job tracking for async mode
jobs = {}
models_ready = False


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy" if models_ready else "initializing",
        "models_ready": models_ready,
        "mode": "pod-http",
        "jobs_pending": sum(1 for j in jobs.values() if j["status"] == "IN_PROGRESS"),
        "jobs_completed": sum(1 for j in jobs.values() if j["status"] == "COMPLETED"),
    })


@app.route("/runsync", methods=["POST"])
def runsync():
    """Synchronous generation — blocks until complete."""
    data = request.get_json()
    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in request body"}), 400

    if not models_ready:
        return jsonify({"error": "Models still initializing, try again later"}), 503

    job_id = str(uuid.uuid4())
    job = {"id": job_id, "input": data["input"]}

    try:
        result = serverless_handler(job)
        return jsonify({
            "id": job_id,
            "status": "COMPLETED",
            "output": result
        })
    except Exception as e:
        return jsonify({
            "id": job_id,
            "status": "FAILED",
            "error": str(e)
        }), 500


@app.route("/generate", methods=["POST"])
@app.route("/run", methods=["POST"])
def generate_async():
    """Async generation — returns job ID immediately."""
    data = request.get_json()
    if not data or "input" not in data:
        return jsonify({"error": "Missing 'input' in request body"}), 400

    if not models_ready:
        return jsonify({"error": "Models still initializing, try again later"}), 503

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "IN_PROGRESS", "output": None, "error": None}

    def run_job():
        try:
            job = {"id": job_id, "input": data["input"]}
            result = serverless_handler(job)
            jobs[job_id] = {"status": "COMPLETED", "output": result, "error": None}
        except Exception as e:
            jobs[job_id] = {"status": "FAILED", "output": None, "error": str(e)}

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()

    return jsonify({"id": job_id, "status": "IN_QUEUE"})


@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    """Check status of an async job."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    job = jobs[job_id]
    response = {"id": job_id, "status": job["status"]}
    if job["output"]:
        response["output"] = job["output"]
    if job["error"]:
        response["error"] = job["error"]
    return jsonify(response)


if __name__ == "__main__":
    print("PlotProse MagiHuman Pod Server starting...")
    print(f"Mode: HTTP Server (regular GPU pod)")

    # Ensure models on startup
    models_ready = ensure_models()
    if not models_ready:
        print("WARNING: Models not available. Will return 503 until ready.")

    port = int(os.environ.get("PORT", "8000"))
    print(f"Listening on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
