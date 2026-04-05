#!/usr/bin/env python3
"""RunPod Serverless Handler for daVinci-MagiHuman"""
import os, sys, json, subprocess, tempfile, base64
import runpod, requests

MODEL_DIR = os.environ.get("MODEL_DIR", "/runpod-volume/models")
ASSETS_DIR = os.environ.get("ASSETS_DIR", "/runpod-volume/assets")
DEFAULT_BRAND_FACE = os.path.join(ASSETS_DIR, "brand_face.png")
OUTPUT_DIR = "/workspace/output"

def ensure_models():
    marker = os.path.join(MODEL_DIR, ".download_complete")
    if os.path.exists(marker):
        print(f"Models already present at {MODEL_DIR}")
        return True
    print("First cold start - downloading model weights...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    try:
        result = subprocess.run(["bash", "/workspace/download_models.sh", MODEL_DIR], capture_output=True, text=True, timeout=3600)
        if result.returncode == 0:
            with open(marker, "w") as f: f.write("done")
            return True
        else:
            print(f"Download failed: {result.stderr[-1000:]}")
            return False
    except subprocess.TimeoutExpired:
        return False

def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    return dest

def handler(job):
    inp = job["input"]
    prompt = inp.get("prompt", "")
    image_url = inp.get("image_url")
    resolution = inp.get("resolution", "540p")
    duration = inp.get("duration", 5)
    vid = inp.get("variation_id", "single")
    if not prompt: return {"error": "No prompt provided"}
    if image_url:
        image_path = os.path.join(tempfile.gettempdir(), "input_face.png")
        try: download_file(image_url, image_path)
        except Exception as e: return {"error": str(e)}
    elif os.path.exists(DEFAULT_BRAND_FACE): image_path = DEFAULT_BRAND_FACE
    else: return {"error": "No image and no default brand face"}
    from generate_avatar import generate_single
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, f"{vid}_{resolution}.mp4")
    ok = generate_single(prompt=prompt, image_path=image_path, output_path=out, resolution=resolution, model_dir=MODEL_DIR, duration=duration)
    if ok and os.path.exists(out):
        with open(out, "rb") as f: v = base64.b64encode(f.read()).decode()
        return {"status": "success", "video_base64": v, "resolution": resolution, "variation_id": vid}
    return {"status": "error", "message": "Generation failed", "variation_id": vid}

print("PlotProse MagiHuman Worker starting...")
ensure_models()
os.makedirs(ASSETS_DIR, exist_ok=True)
runpod.serverless.start({"handler": handler})
