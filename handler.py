#!/usr/bin/env python3
"""
RunPod Handler for daVinci-MagiHuman
Downloads ~40GB models on first start, then processes avatar generation jobs.
Robust: checks disk space, falls back to container disk, streams download logs.
"""

import os, sys, json, shutil, subprocess, logging, time, traceback, tempfile
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger("handler")

MODEL_DIR = os.environ.get("MODEL_DIR", "/runpod-volume/models")
ASSETS_DIR = os.environ.get("ASSETS_DIR", "/runpod-volume/assets")
DEFAULT_BRAND_FACE = os.path.join(ASSETS_DIR, "brand_face.png")
OUTPUT_DIR = "/workspace/output"
MAGIHUMAN_DIR = "/workspace/daVinci-MagiHuman"
MIN_DISK_GB = 45


def get_disk_free_gb(path):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return 0


def get_model_dir():
    try:
        os.makedirs(MODEL_DIR, exist_ok=True)
        test = os.path.join(MODEL_DIR, ".write_test")
        with open(test, "w") as f: f.write("ok")
        os.remove(test)
        free_gb = get_disk_free_gb(MODEL_DIR)
        log.info(f"Using network volume: {MODEL_DIR} ({free_gb:.1f}GB free)")
        return MODEL_DIR
    except Exception as e:
        log.warning(f"Network volume not available: {e}")
    fallback = "/workspace/models"
    os.makedirs(fallback, exist_ok=True)
    free_gb = get_disk_free_gb(fallback)
    log.info(f"Using container disk: {fallback} ({free_gb:.1f}GB free)")
    return fallback


def ensure_models():
    try:
        model_dir = get_model_dir()
        marker = os.path.join(model_dir, ".download_complete")
        if os.path.exists(marker):
            log.info(f"Models already present at {model_dir}")
            return True
        free_gb = get_disk_free_gb(model_dir)
        if free_gb < MIN_DISK_GB:
            log.error(f"Insufficient disk: {free_gb:.1f}GB free, need {MIN_DISK_GB}GB")
            log.error("Deploy with containerDiskInGb >= 100 or attach network volume")
            return False
        log.info(f"First cold start - downloading models to {model_dir}")
        log.info(f"Disk: {free_gb:.1f}GB free. This takes ~15-20 min.")
        script = "/workspace/download_models.sh"
        if not os.path.exists(script):
            log.error(f"Download script not found: {script}")
            return False
        process = subprocess.Popen(["bash", script, model_dir], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            line = line.rstrip()
            if line: log.info(f"[download] {line}")
        returncode = process.wait(timeout=3600)
        if returncode == 0:
            with open(marker, "w") as f: f.write(f"completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            log.info("Model download complete!")
            log.info(f"Disk after download: {get_disk_free_gb(model_dir):.1f}GB free")
            return True
        else:
            log.error(f"Download script exited with code {returncode}")
            return False
    except subprocess.TimeoutExpired:
        log.error("Model download timed out after 1 hour")
        try: process.kill()
        except: pass
        return False
    except Exception as e:
        log.error(f"Unexpected error in ensure_models: {e}")
        log.debug(traceback.format_exc())
        return False


def download_file(url, dest):
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
    return dest


def handler(job):
    job_input = job["input"]
    prompt = job_input.get("prompt", "")
    image_url = job_input.get("image_url", None)
    resolution = job_input.get("resolution", "540p")
    duration = job_input.get("duration", 5)
    variation_id = job_input.get("variation_id", "single")
    if not prompt: return {"error": "No prompt provided"}
    if image_url:
        image_path = os.path.join(tempfile.gettempdir(), "input_face.png")
        try: download_file(image_url, image_path)
        except Exception as e: return {"error": f"Failed to download image: {str(e)}"}
    elif os.path.exists(DEFAULT_BRAND_FACE):
        image_path = DEFAULT_BRAND_FACE
    else:
        return {"error": "No image provided and no default brand face at " + DEFAULT_BRAND_FACE}
    from generate_avatar import generate_single
    model_dir = get_model_dir()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{variation_id}_{resolution}.mp4")
    success = generate_single(prompt=prompt, image_path=image_path, output_path=output_path, resolution=resolution, model_dir=model_dir, duration=duration)
    if success and os.path.exists(output_path):
        import base64
        with open(output_path, "rb") as f: video_b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"status": "success", "video_base64": video_b64, "resolution": resolution, "variation_id": variation_id}
    else:
        return {"status": "error", "message": "Video generation failed", "variation_id": variation_id}


if __name__ == "__main__":
    import runpod
    log.info("PlotProse MagiHuman Worker starting (serverless mode)...")
    log.info(f"Model dir: {MODEL_DIR}")
    models_ready = ensure_models()
    if not models_ready: log.warning("Models not available. Jobs will fail.")
    os.makedirs(ASSETS_DIR, exist_ok=True)
    runpod.serverless.start({"handler": handler})
