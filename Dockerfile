FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

ENV MEDIARIVER_STATE_DB=/data/state.db
ENV MEDIARIVER_WORKFLOWS_DIR=/workflows

VOLUME ["/data", "/workflows", "/work"]

ENTRYPOINT ["mediariver"]
CMD ["run", "--workflows-dir", "/workflows"]
