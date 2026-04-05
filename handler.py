#!/usr/bin/env python3
"""RunPod Serverless Handler for daVinci-MagiHuman
Handles cold-start bootstrap, model download, and avatar generation."""
import os, sys, json, subprocess, tempfile, base64, time
import runpod
import requests

MODEL_DIR = os.environ.get("MODEL_DIR", "/runpod-volume/models")
ASSETS_DIR = os.environ.get("ASSETS_DIR", "/runpod-volume/assets")
OUTPUT_DIR = "/workspace/output"
MAGIHUMAN_DIR = "/workspace/daVinci-MagiHuman"

def bootstrap():
    """Install MagiHuman stack on cold start (not baked into slim image)."""
    if os.path.exists(os.path.join(MAGIHUMAN_DIR, "requirements.txt")):
        print("MagiHuman already installed, skipping bootstrap")
        return True
    print("=== Cold start bootstrap ===")
    try:
        subprocess.run(["git", "clone", "https://github.com/GAIR-NLP/daVinci-MagiHuman.git", MAGIHUMAN_DIR],
            check=True, capture_output=True, text=True, timeout=300)
        subprocess.run(["pip", "install", "--no-cache-dir", "-r", f"{MAGIHUMAN_DIR}/requirements.txt"],
            capture_output=True, text=True, timeout=600)
        subprocess.run(["git", "clone", "https://github.com/SandAI-org/MagiCompiler.git", "/workspace/MagiCompiler"],
            capture_output=True, text=True, timeout=300)
        subprocess.run(["pip", "install", "--no-cache-dir", "-r", "/workspace/MagiCompiler/requirements.txt"],
            capture_output=True, text=True, timeout=600)
        subprocess.run(["pip", "install", "--no-cache-dir", "/workspace/MagiCompiler"],
            capture_output=True, text=True, timeout=300)
        print("=== Bootstrap complete ===")
        return True
    except Exception as e:
        print(f"Bootstrap error: {e}")
        return False

def ensure_models():
    """Download model weights to network volume on first run."""
    marker = os.path.join(MODEL_DIR, ".download_complete")
    if os.path.exists(marker):
        print(f"Models ready at {MODEL_DIR}")
        return True
    print("Downloading models (first run only)...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    try:
        result = subprocess.run(["bash", "/workspace/download_models.sh", MODEL_DIR],
            capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            with open(marker, "w") as f:
                f.write("done")
            return True
        print(f"Download failed: {result.stderr[-500:]}")
        return False
    except subprocess.TimeoutExpired:
        print("Model download timed out")
        return False

def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def handler(job):
    inp = job["input"]
    prompt = inp.get("prompt", "")
    image_url = inp.get("image_url")
    resolution = inp.get("resolution", "540p")
    duration = inp.get("duration", 5)
    variation_id = inp.get("variation_id", "single")

    if not prompt:
        return {"error": "No prompt provided"}

    # Get input image
    if image_url:
        image_path = os.path.join(tempfile.gettempdir(), "input_face.png")
        try:
            download_file(image_url, image_path)
        except Exception as e:
            return {"error": f"Image download failed: {e}"}
    else:
        return {"error": "No image_url provided"}

    # Generate avatar video
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{variation_id}_{resolution}.mp4")

    config_map = {"256p": "example/distill", "540p": "example/sr_540p", "1080p": "example/sr_1080p"}
    config_dir = config_map.get(resolution, "example/base")
    run_script = os.path.join(MAGIHUMAN_DIR, config_dir, "run.sh")

    if os.path.exists(run_script):
        env = os.environ.copy()
        env.update({"PROMPT": prompt, "IMAGE_PATH": image_path,
                     "OUTPUT_PATH": output_path, "MODEL_DIR": MODEL_DIR})
        result = subprocess.run(["bash", run_script], cwd=MAGIHUMAN_DIR,
            env=env, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr[-300:], "variation_id": variation_id}
    else:
        return {"status": "error", "message": f"No run script at {run_script}", "variation_id": variation_id}

    if os.path.exists(output_path):
        with open(output_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("utf-8")
        return {"status": "success", "video_base64": video_b64,
                "resolution": resolution, "variation_id": variation_id}
    return {"status": "error", "message": "No output file generated", "variation_id": variation_id}

# === Startup ===
print("PlotProse MagiHuman Worker starting...")
bootstrap_ok = bootstrap()
if not bootstrap_ok:
    print("WARNING: Bootstrap failed - handler may not work correctly")
models_ready = ensure_models()
if not models_ready:
    print("WARNING: Models not available - generation will fail")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
print("Handler ready, accepting jobs...")
runpod.serverless.start({"handler": handler})
