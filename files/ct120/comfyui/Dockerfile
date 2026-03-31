FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    COMFYUI_HOME=/opt/ComfyUI \
    VENV_PATH=/opt/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv "${VENV_PATH}"

ENV PATH="${VENV_PATH}/bin:${PATH}"

RUN git clone https://github.com/comfy-org/ComfyUI.git "${COMFYUI_HOME}"

WORKDIR ${COMFYUI_HOME}

RUN pip install --upgrade pip setuptools wheel \
 && pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 \
 && pip install -r requirements.txt

EXPOSE 8188

CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
