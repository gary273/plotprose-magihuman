# PlotProse MagiHuman - RunPod Serverless Worker
# Generates talking avatar videos from photo + text/audio
# Model weights live on network volume; code + deps baked into image

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

# System dependencies
RUN apt-get update && apt-get install -y \
    git wget curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Clone and install MagiHuman stack
RUN git clone https://github.com/GAIR-NLP/daVinci-MagiHuman.git /workspace/daVinci-MagiHuman && \
    cd /workspace/daVinci-MagiHuman && \
    pip install --no-cache-dir -r requirements.txt || true

# Install MagiCompiler (inference engine)
RUN git clone https://github.com/SandAI-org/MagiCompiler.git /workspace/MagiCompiler && \
    cd /workspace/MagiCompiler && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# RunPod SDK + utilities
RUN pip install --no-cache-dir runpod requests huggingface_hub

# Copy our custom scripts
COPY handler.py /workspace/handler.py
COPY generate_avatar.py /workspace/generate_avatar.py
COPY download_models.sh /workspace/download_models.sh
RUN chmod +x /workspace/download_models.sh

# Default: start the RunPod serverless handler
CMD ["python", "-u", "/workspace/handler.py"]
