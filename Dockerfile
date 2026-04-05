# PlotProse MagiHuman - RunPod Serverless Worker
# Slim image: Python 3.11 + CUDA runtime + runpod SDK + bootstrap
# Model weights + MagiHuman repos are installed at cold start via bootstrap.sh

FROM python:3.11-slim

WORKDIR /workspace

# System deps (keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# RunPod SDK + utilities (this is what makes it a serverless worker)
RUN pip install --no-cache-dir runpod requests huggingface_hub

# Copy our handler and bootstrap scripts
COPY handler.py /workspace/handler.py
COPY generate_avatar.py /workspace/generate_avatar.py
COPY download_models.sh /workspace/download_models.sh
RUN chmod +x /workspace/download_models.sh

# The handler calls runpod.serverless.start() which registers with RunPod
CMD ["python", "-u", "/workspace/handler.py"]
