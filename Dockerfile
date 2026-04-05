FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

RUN apt-get update && apt-get install -y git wget curl ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip --version && python --version && pip config list

RUN pip install --no-cache-dir --break-system-packages runpod requests huggingface_hub flask 2>&1 || \
    pip install --no-cache-dir runpod requests huggingface_hub flask 2>&1 || \
    (python -m pip install --no-cache-dir runpod requests huggingface_hub flask 2>&1 || \
     echo 'ALL PIP METHODS FAILED')

RUN python -c 'import runpod; print("runpod ok")' 2>&1 || echo 'runpod not available'
RUN python -c 'import flask; print("flask ok")' 2>&1 || echo 'flask not available'

COPY handler.py /workspace/handler.py
COPY generate_avatar.py /workspace/generate_avatar.py
COPY download_models.sh /workspace/download_models.sh
COPY pod_server.py /workspace/pod_server.py
COPY start.sh /workspace/start.sh
RUN chmod +x /workspace/download_models.sh /workspace/start.sh

EXPOSE 8000

CMD ["/workspace/start.sh"]
