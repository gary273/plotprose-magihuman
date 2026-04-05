#!/bin/bash
# Download MagiHuman model weights to RunPod network volume
# Run ONCE on first cold start - models persist on network volume
# Usage: bash download_models.sh /runpod-volume/models

MODEL_DIR="${1:-/runpod-volume/models}"
mkdir -p "$MODEL_DIR"

echo "Downloading daVinci-MagiHuman model weights to $MODEL_DIR"

pip install -q huggingface_hub

python3 -c "
from huggingface_hub import snapshot_download
import os
model_dir = '$MODEL_DIR'

print('Downloading daVinci-MagiHuman models...')
snapshot_download(repo_id='GAIR/daVinci-MagiHuman', local_dir=os.path.join(model_dir, 'daVinci-MagiHuman'), local_dir_use_symlinks=False)

print('Downloading text encoder (t5gemma)...')
snapshot_download(repo_id='sand-ai/t5gemma-9b-9b-ul2', local_dir=os.path.join(model_dir, 't5gemma-9b-9b-ul2'), local_dir_use_symlinks=False)

print('Downloading audio model (stable-audio-open)...')
snapshot_download(repo_id='stabilityai/stable-audio-open-1.0', local_dir=os.path.join(model_dir, 'stable-audio-open-1.0'), local_dir_use_symlinks=False)

print('Downloading VAE (Wan2.2-TI2V-5B)...')
snapshot_download(repo_id='Wan-AI/Wan2.2-TI2V-5B', local_dir=os.path.join(model_dir, 'Wan2.2-TI2V-5B'), local_dir_use_symlinks=False, allow_patterns=['*vae*', '*tokenizer*', 'config.json'])

print('All models downloaded!')
os.system(f'du -sh {model_dir}')
"

echo "Model download complete! Saved to: $MODEL_DIR"
