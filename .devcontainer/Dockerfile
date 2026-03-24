FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY pyproject.toml .
COPY src/ src/

RUN pip install -e ".[dev]"
