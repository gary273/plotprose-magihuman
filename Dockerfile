# PlotProse MagiHuman — RunPod GPU Worker
# Dual-mode: serverless handler OR HTTP server (regular pod)
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

# RunPod SDK + HTTP server + utilities
RUN pip install --no-cache-dir runpod requests huggingface_hub flask

# Copy our custom scripts
COPY handler.py /workspace/handler.py
COPY generate_avatar.py /workspace/generate_avatar.py
COPY download_models.sh /workspace/download_models.sh
COPY pod_server.py /workspace/pod_server.py
COPY start.sh /workspace/start.sh
RUN chmod +x /workspace/download_models.sh /workspace/start.sh

# Expose HTTP port for pod mode
EXPOSE 8000

# Default: auto-detect mode via start.sh
CMD ["/workspace/start.sh"]
