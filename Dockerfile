# PlotProse MagiHuman — RunPod GPU Worker
# Dual-mode: serverless handler OR HTTP server (regular pod)
# Model weights live on network volume; code + deps baked into image

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

# System dependencies
RUN apt-get update && apt-get install -y \
    git wget curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# CRITICAL: Install our core deps FIRST before research repos
# Research repos may have conflicting requirements that break pip
RUN pip install --no-cache-dir runpod requests huggingface_hub flask

# Clone MagiHuman stack (may fail if repo is private/unavailable)
RUN git clone https://github.com/GAIR-NLP/daVinci-MagiHuman.git /workspace/daVinci-MagiHuman || \
    (echo "WARNING: Could not clone daVinci-MagiHuman" && mkdir -p /workspace/daVinci-MagiHuman)

RUN if [ -f /workspace/daVinci-MagiHuman/requirements.txt ]; then \
      cd /workspace/daVinci-MagiHuman && pip install --no-cache-dir -r requirements.txt || true; \
    fi

# Clone and install MagiCompiler (inference engine)
RUN git clone https://github.com/SandAI-org/MagiCompiler.git /workspace/MagiCompiler || \
    (echo "WARNING: Could not clone MagiCompiler" && mkdir -p /workspace/MagiCompiler)

RUN if [ -f /workspace/MagiCompiler/requirements.txt ]; then \
      cd /workspace/MagiCompiler && pip install --no-cache-dir -r requirements.txt || true; \
    fi

RUN if [ -f /workspace/MagiCompiler/setup.py ] || [ -f /workspace/MagiCompiler/pyproject.toml ]; then \
      cd /workspace/MagiCompiler && pip install --no-cache-dir . || true; \
    fi

# Re-ensure our critical deps are intact after research repo installs
RUN pip install --no-cache-dir --force-reinstall runpod flask

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
