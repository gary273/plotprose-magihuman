#!/usr/bin/env python3
"""PlotProse Avatar Generator - wrapper around daVinci-MagiHuman"""
import argparse, json, os, subprocess, shutil, time
from pathlib import Path

DEFAULT_MODEL_DIR = "/runpod-volume/models"
MAGIHUMAN_DIR = "/workspace/daVinci-MagiHuman"

def generate_single(prompt, image_path, output_path, resolution="540p", model_dir=DEFAULT_MODEL_DIR, duration=5):
    print(f"Generating avatar: {prompt[:60]}... @ {resolution}")
    start = time.time()
    if resolution == "256p": config_dir = "example/distill"
    elif resolution == "540p": config_dir = "example/sr_540p"
    elif resolution == "1080p": config_dir = "example/sr_1080p"
    else: config_dir = "example/base"
    run_script = os.path.join(MAGIHUMAN_DIR, config_dir, "run.sh")
    if os.path.exists(run_script):
        env = os.environ.copy()
        env["PROMPT"] = prompt
        env["IMAGE_PATH"] = image_path or ""
        env["OUTPUT_PATH"] = output_path
        env["MODEL_DIR"] = model_dir
        result = subprocess.run(["bash", run_script], cwd=MAGIHUMAN_DIR, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr[-500:]}")
            return False
    print(f"Generated in {time.time()-start:.1f}s")
    return True

def generate_batch(ad_copy_json, image_path, output_dir, resolution="540p", model_dir=DEFAULT_MODEL_DIR, max_variations=None):
    with open(ad_copy_json) as f: data = json.load(f)
    variations = data.get("variations", [])
    if max_variations: variations = variations[:max_variations]
    os.makedirs(output_dir, exist_ok=True)
    print(f"BATCH: {len(variations)} variations @ {resolution}")
    results = []
    start = time.time()
    for i, v in enumerate(variations):
        vid = v.get("id", f"v{i:03d}")
        prompt = f"{v.get('headline','')}. {v.get('body','')}"
        out = os.path.join(output_dir, f"{vid}_avatar_{resolution}.mp4")
        print(f"[{i+1}/{len(variations)}] {vid}...")
        ok = generate_single(prompt=prompt, image_path=image_path, output_path=out, resolution=resolution, model_dir=model_dir)
        results.append({"id": vid, "framework": v.get("framework",""), "output_path": out, "success": ok, "resolution": resolution})
    elapsed = time.time() - start
    manifest = {"product": data.get("metadata",{}), "brand_face": image_path, "resolution": resolution,
        "total_generated": sum(1 for r in results if r["success"]),
        "total_failed": sum(1 for r in results if not r["success"]),
        "total_time_seconds": round(elapsed,1), "renders": results}
    manifest_path = os.path.join(output_dir, "avatar_manifest.json")
    with open(manifest_path, "w") as f: json.dump(manifest, f, indent=2)
    print(f"BATCH DONE: {manifest['total_generated']}/{len(variations)} in {elapsed:.1f}s")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlotProse Avatar Generator")
    parser.add_argument("--prompt", type=str)
    parser.add_argument("--batch", type=str)
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--output", type=str)
    parser.add_argument("--output-dir", type=str)
    parser.add_argument("--resolution", default="540p", choices=["256p","540p","1080p"])
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    parser.add_argument("--max", type=int)
    parser.add_argument("--duration", type=int, default=5)
    args = parser.parse_args()
    if args.batch:
        generate_batch(args.batch, args.image, args.output_dir or "/workspace/output/avatars", args.resolution, args.model_dir, args.max)
    elif args.prompt:
        generate_single(args.prompt, args.image, args.output or "/workspace/output/avatar.mp4", args.resolution, args.model_dir, args.duration)
    else:
        print("Provide --prompt or --batch")
