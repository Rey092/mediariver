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


# --- GPU image (NVIDIA CUDA + NVENC + AI upscale) ---
FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04 AS gpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    ffmpeg \
    exiftool \
    imagemagick \
    libnvidia-encode-570 \
    libpq-dev \
    wget unzip \
    # Vulkan loader for realesrgan-ncnn-vulkan GPU acceleration
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Register NVIDIA Vulkan ICD — the container toolkit mounts the driver lib
# but doesn't create the ICD manifest, so Vulkan can't discover the GPU
RUN mkdir -p /etc/vulkan/icd.d && \
    echo '{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0","api_version":"1.3.277"}}' \
    > /etc/vulkan/icd.d/nvidia_icd.json

# Install Real-ESRGAN (AI upscaler for manga/anime art)
RUN wget -q https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && unzip -q realesrgan-ncnn-vulkan-*.zip -d /opt/realesrgan \
    && chmod +x /opt/realesrgan/realesrgan-ncnn-vulkan \
    && ln -s /opt/realesrgan/realesrgan-ncnn-vulkan /usr/local/bin/realesrgan-ncnn-vulkan \
    && rm realesrgan-ncnn-vulkan-*.zip

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --break-system-packages "setuptools<81" && \
    pip install --no-cache-dir --break-system-packages torch --index-url https://download.pytorch.org/whl/cu126 && \
    pip install --no-cache-dir --break-system-packages ".[postgres,cuda]"

ENV MEDIARIVER_WORKFLOWS_DIR=/workflows
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=video,compute,utility,graphics

VOLUME ["/data", "/workflows", "/work"]

ENTRYPOINT ["mediariver"]
CMD ["run", "--workflows-dir", "/workflows"]
