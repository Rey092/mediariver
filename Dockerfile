# --- CPU-only image (default) ---
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir "setuptools<81" && pip install --no-cache-dir .

ENV MEDIARIVER_STATE_DB=/data/state.db
ENV MEDIARIVER_WORKFLOWS_DIR=/workflows

VOLUME ["/data", "/workflows", "/work"]

ENTRYPOINT ["mediariver"]
CMD ["run", "--workflows-dir", "/workflows"]


# --- GPU image (NVIDIA CUDA + NVENC) ---
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04 AS gpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    ffmpeg \
    exiftool \
    libnvidia-encode-570 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --break-system-packages "setuptools<81" && \
    pip install --no-cache-dir --break-system-packages .

ENV MEDIARIVER_STATE_DB=/data/state.db
ENV MEDIARIVER_WORKFLOWS_DIR=/workflows
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=video,compute,utility

VOLUME ["/data", "/workflows", "/work"]

ENTRYPOINT ["mediariver"]
CMD ["run", "--workflows-dir", "/workflows"]
