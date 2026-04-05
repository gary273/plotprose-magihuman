FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace

RUN apt-get update && apt-get install -y git wget curl ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip --version && python --version

RUN pip install --no-cache-dir runpod || echo WARN_runpod
RUN pip install --no-cache-dir requests || echo WARN_requests
RUN pip install --no-cache-dir huggingface_hub || echo WARN_hf
RUN pip install --no-cache-dir flask || echo WARN_flask

RUN python -c 'import runpod; import flask; import requests; print("ALL OK")'

COPY handler.py /workspace/handler.py
COPY generate_avatar.py /workspace/generate_avatar.py
COPY download_models.sh /workspace/download_models.sh
COPY pod_server.py /workspace/pod_server.py
COPY start.sh /workspace/start.sh
RUN chmod +x /workspace/download_models.sh /workspace/start.sh

EXPOSE 8000

CMD ["/workspace/start.sh"]
