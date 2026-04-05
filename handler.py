#!/usr/bin/env python3
"""
RunPod Serverless Handler for daVinci-MagiHuman
Accepts jobs via RunPod's serverless API and generates avatar videos.

On cold start: checks if model weights exist on network volume.
If not, downloads them (~40GB, one-time ~15-20 min).
Subsequent cold starts skip the download.

Job input format:
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
import subprocess
import base64
import runpod
import requests
import tempfile

# Paths — network volume mounts at /runpod-volume
MODEL_DIR = os.environ.get("MODEL_DIR", "/runpod-volume/models")
ASSETS_DIR = os.environ.get("ASSETS_DIR", "/runpod-volume/assets")
DEFAULT_BRAND_FACE = os.path.join(ASSETS_DIR, "brand_face.png")
OUTPUT_DIR = "/workspace/output"
MAGIHUMAN_DIR = "/workspace/daVinci-MagiHuman"


def ensure_models():
    """Download model weights to network volume if they don't exist yet."""
    marker = os.path.join(MODEL_DIR, ".download_complete")
    if os.path.exists(marker):
        print(f"Models already present at {MODEL_DIR}")
        return True

    print("First cold start — downloading model weights to network volume...")
    print("This takes ~15-20 minutes. Subsequent starts will be fast.")

    os.makedirs(MODEL_DIR, exist_ok=True)

    try:
        result = subprocess.run(
            ["bash", "/workspace/download_models.sh", MODEL_DIR],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max
        )
        if result.returncode == 0:
            # Write marker file so we don't re-download
            with open(marker, "w") as f:
                f.write("done")
            print("Model download complete!")
            return True
        else:
            print(f"Model download failed: {result.stderr[-1000:]}")
            return False
    except subprocess.TimeoutExpired:
        print("Model download timed out after 1 hour")
        return False


def download_file(url: str, dest: str):
    """Download a file from URL to local path."""
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


def handler(job):
    """RunPod serverless handler — processes avatar generation jobs."""
    job_input = job["input"]

    prompt = job_input.get("prompt", "")
    image_url = job_input.get("image_url", None)
    resolution = job_input.get("resolution", "540p")
    duration = job_input.get("duration", 5)
    variation_id = job_input.get("variation_id", "single")

    if not prompt:
        return {"error": "No prompt provided"}

    # Handle image — use URL, default brand face, or error
    if image_url:
        image_path = os.path.join(tempfile.gettempdir(), "input_face.png")
        try:
            download_file(image_url, image_path)
        except Exception as e:
            return {"error": f"Failed to download image: {str(e)}"}
    elif os.path.exists(DEFAULT_BRAND_FACE):
        image_path = DEFAULT_BRAND_FACE
    else:
        return {"error": "No image provided and no default brand face found at " + DEFAULT_BRAND_FACE}

    # Import generation function
    from generate_avatar import generate_single

    # Generate
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{variation_id}_{resolution}.mp4")

    success = generate_single(
        prompt=prompt,
        image_path=image_path,
        output_path=output_path,
        resolution=resolution,
        model_dir=MODEL_DIR,
        duration=duration,
    )

    if success and os.path.exists(output_path):
        # Try uploading to Supabase Storage first; fall back to base64
        video_url = None
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        job_id = job.get("id", variation_id)

        if supabase_url and supabase_key:
            try:
                storage_path = f"avatars/{job_id}.mp4"
                upload_url = f"{supabase_url}/storage/v1/object/generated-videos/{storage_path}"
                with open(output_path, "rb") as f:
                    resp = requests.post(upload_url, data=f, headers={
                        "Authorization": f"Bearer {supabase_key}",
                        "Content-Type": "video/mp4",
                        "x-upsert": "true",
                    }, timeout=120)
                if resp.status_code in (200, 201):
                    video_url = f"{supabase_url}/storage/v1/object/public/generated-videos/{storage_path}"
                    print(f"Uploaded to Supabase Storage: {video_url}")
                else:
                    print(f"Supabase upload failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"Supabase upload error: {e}")

        result = {
            "status": "success",
            "resolution": resolution,
            "variation_id": variation_id,
        }
        if video_url:
            result["video_url"] = video_url
        else:
            # Fallback: return base64 (orchestrator will handle upload)
            with open(output_path, "rb") as f:
                result["video_base64"] = base64.b64encode(f.read()).decode("utf-8")
        return result
    else:
        return {
            "status": "error",
            "message": "Video generation failed",
            "variation_id": variation_id,
        }


# --- Startup (only when run directly, not when imported) ---
if __name__ == "__main__":
    print("PlotProse MagiHuman Worker starting (serverless mode)...")
    print(f"Model dir: {MODEL_DIR}")
    print(f"Network volume contents: {os.listdir('/runpod-volume') if os.path.exists('/runpod-volume') else 'NOT MOUNTED'}")

    # Ensure models are downloaded before accepting jobs
    models_ready = ensure_models()
    if not models_ready:
        print("WARNING: Models not available. Jobs will fail until models are downloaded.")

    # Ensure assets directory exists
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Start the RunPod serverless handler
    runpod.serverless.start({"handler": handler})
