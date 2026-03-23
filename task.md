# MediaFlow — Spec-Driven Media Pipeline CLI

## What is this

A Python CLI server that watches directories, picks up media files, and runs processing workflows defined in YAML specs. Think `docker-compose` but for file/media pipelines.

Core principles:
- YAML-first — workflows are specs in a `workflows/` folder, Git-friendly, AI-friendly
- Batteries included — ships with predefined actions for common media ops (transcode, HLS, thumbnail, upscale, etc.)
- Pluggable filesystems — local, S3, FTP, SFTP via [PyFilesystem2](https://github.com/PyFilesystem/pyfilesystem2)
- Docker-native — each action backed by a container image, auto-pulled if binary not available locally
- Idempotent — tracks already-processed files, never reprocesses unless forced

## Project Structure

```
mediaflow/
├── src/
│   └── mediaflow/
│       ├── __init__.py
│       ├── __main__.py                  # `python -m mediaflow` entrypoint
│       ├── cli.py                       # click/typer CLI definition
│       ├── config/
│       │   ├── __init__.py
│       │   ├── loader.py                # YAML parsing, env var interpolation
│       │   ├── schema.py                # pydantic models for workflow specs
│       │   └── validators.py            # cross-field validation (connections exist, etc.)
│       ├── connections/
│       │   ├── __init__.py
│       │   ├── registry.py              # connection type -> handler mapping
│       │   ├── base.py                  # abstract base (wraps pyfilesystem2 FS objects)
│       │   ├── local.py
│       │   ├── s3.py                    # fs-s3fs wrapper
│       │   ├── ftp.py                   # built-in fs FTP
│       │   └── sftp.py                  # fs.sshfs wrapper
│       ├── actions/
│       │   ├── __init__.py
│       │   ├── registry.py              # action name -> handler mapping
│       │   ├── base.py                  # abstract base action
│       │   │
│       │   │   # --- Filesystem actions ---
│       │   ├── copy.py                  # cross-filesystem copy
│       │   ├── delete.py                # remove file from any connection
│       │   ├── move.py                  # copy + delete
│       │   │
│       │   │   # --- Video actions ---
│       │   ├── video_info.py            # ffprobe: extract codec, resolution, duration, bitrate, fps, HDR metadata
│       │   ├── video_crop.py            # aspect ratio crop (4:3→16:9, letterbox removal, auto-detect black bars)
│       │   ├── transcode.py             # ffmpeg presets (h265-fast, h264-web, h265-10bit, nvenc-h264, nvenc-h265, etc.)
│       │   ├── hls.py                   # HLS multi-variant generation (360p/480p/720p/1080p + master playlists)
│       │   ├── upscale.py               # anime upscale: Dandere2x (GPU, docker), Real-ESRGAN fallback, lanczos last resort
│       │   ├── thumbnail.py             # frame extraction at timestamp, grid/sprite thumbnails for scrubber
│       │   ├── video_extract_audio.py   # demux audio stream(s) from video container
│       │   ├── subtitle_extract.py      # extract subtitle tracks (SRT/ASS/VTT) from MKV/MP4
│       │   ├── video_concat.py          # concatenate video segments (demuxer or filter_complex)
│       │   ├── video_preview.py         # generate short GIF/WebP preview clip (hover thumbnails)
│       │   │
│       │   │   # --- Audio actions ---
│       │   ├── audio_info.py            # ffprobe: extract codec, bitrate, sample rate, channels, duration
│       │   ├── audio_normalize.py       # EBU R128 2-pass loudnorm (I=-16, TP=-1.5, LRA=11)
│       │   ├── audio_convert.py         # convert between codecs (AAC, MP3, FLAC, OGG, WAV, OPUS)
│       │   ├── audio_hls.py             # audio-only HLS packaging (128k/256k variants + master playlist)
│       │   ├── audio_tag.py             # write/rewrite ID3/Vorbis metadata tags
│       │   ├── audio_embed_art.py       # embed cover art into audio file metadata
│       │   ├── audio_duration_check.py  # compare input vs output duration (detect truncation/corruption)
│       │   │
│       │   │   # --- Image actions ---
│       │   ├── image_info.py            # identify: width, height, format, colorspace, pixel count
│       │   ├── image_convert.py         # convert between formats (JPEG, PNG, WebP, AVIF, JXL)
│       │   ├── image_resize.py          # resize/scale with configurable filter (lanczos, catmullrom)
│       │   ├── image_crop.py            # auto-crop white/black borders, or manual crop rect
│       │   ├── image_optimize.py        # lossy/lossless compress (mozjpeg, pngquant, cjxl, cavif)
│       │   ├── image_flip_rotate.py     # flip horizontal/vertical, rotate 90/180/270/EXIF-auto
│       │   ├── image_orientation.py     # conditional: is landscape/portrait/square
│       │   ├── image_pixel_check.py     # conditional: total pixels above/below threshold
│       │   │
│       │   │   # --- Shared / utility actions ---
│       │   ├── watermark.py             # overlay image/text on video or image
│       │   ├── strip_metadata.py        # exiftool / ffmpeg metadata strip (EXIF, XMP, ID3)
│       │   ├── ocr.py                   # tesseract wrapper (manga/pornhwa text extraction)
│       │   ├── hash_verify.py           # blake3/md5/sha256 checksum generation and verification
│       │   ├── docker_run.py            # arbitrary docker container execution
│       │   ├── shell_run.py             # arbitrary shell command
│       │   └── http.py                  # http.post, http.get callbacks (webhooks, API notify)
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── runner.py                # sequential flow executor
│       │   ├── context.py               # template context (file.name, file.stem, step outputs)
│       │   ├── template.py              # jinja2/mustache-style {{}} resolver
│       │   ├── conditions.py            # `if:` expression evaluator
│       │   └── errors.py                # retry logic, on_failure handling
│       ├── watcher/
│       │   ├── __init__.py
│       │   ├── poller.py                # interval-based directory polling
│       │   └── filter.py                # extension filtering, glob patterns
│       ├── state/
│       │   ├── __init__.py
│       │   ├── store.py                 # abstract state store interface
│       │   ├── sqlite.py                # default — local SQLite for processed file tracking
│       │   └── models.py                # file_hash, status, timestamps, step results
│       ├── docker/
│       │   ├── __init__.py
│       │   └── manager.py               # pull images, run containers, mount volumes, cleanup
│       └── logging/
│           ├── __init__.py
│           └── setup.py                 # structured logging (structlog)
├── actions/                             # default Dockerfiles for built-in actions
│   ├── ffmpeg/
│   │   └── Dockerfile                   # ffmpeg with libx265, libx264, etc.
│   ├── realesrgan/
│   │   └── Dockerfile                   # Real-ESRGAN with models
│   ├── tesseract/
│   │   └── Dockerfile
│   └── imagemagick/
│       └── Dockerfile
├── workflows/                           # example workflow specs
│   ├── video-pipeline.yaml
│   ├── image-optimize.yaml
│   └── manga-process.yaml
├── tests/
│   ├── conftest.py                      # shared fixtures (tmp dirs, mock S3, sample files)
│   ├── unit/
│   │   ├── test_config_loader.py
│   │   ├── test_schema_validation.py
│   │   ├── test_template.py
│   │   ├── test_conditions.py
│   │   ├── test_context.py
│   │   └── actions/
│   │       ├── test_copy.py
│   │       ├── test_transcode.py
│   │       └── test_hls.py
│   ├── integration/
│   │   ├── test_s3_connection.py        # minio-based S3 tests
│   │   ├── test_ftp_connection.py
│   │   ├── test_watcher.py
│   │   ├── test_state_tracking.py
│   │   └── test_full_pipeline.py        # end-to-end with real containers
│   └── fixtures/
│       ├── sample_video.mp4             # tiny 1-second test video (generated in CI)
│       ├── sample_image.jpg
│       └── workflows/
│           ├── valid_basic.yaml
│           ├── valid_conditional.yaml
│           └── invalid_missing_conn.yaml
├── .devcontainer/
│   ├── devcontainer.json                # VS Code devcontainer config
│   ├── docker-compose.yml               # minio + vsftpd + app for local dev
│   └── Dockerfile                       # dev image with ffmpeg, docker CLI, python
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                       # lint + unit tests on every PR
│   │   ├── integration.yml              # integration tests with docker-compose services
│   │   └── release.yml                  # semantic-release -> build -> push to DockerHub + PyPI
│   └── PULL_REQUEST_TEMPLATE.md
├── Dockerfile                           # production image
├── docker-compose.yml                   # production-ready compose (mediaflow + minio)
├── pyproject.toml                       # project metadata, dependencies, tool configs
├── .releaserc.json                      # semantic-release config
├── CHANGELOG.md                         # auto-generated by semantic-release
├── LICENSE
└── README.md
```

## Persistence & Idempotency

Processed file tracking is the core of reliability. Default backend is SQLite (zero config), stored at `~/.mediaflow/state.db` or configurable via `--state-db` / env var.

### State schema

```sql
CREATE TABLE processed_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name   TEXT NOT NULL,
    file_path       TEXT NOT NULL,          -- original source path
    file_hash       TEXT NOT NULL,          -- blake3 hash of source file
    file_size       INTEGER NOT NULL,
    status          TEXT NOT NULL,          -- pending | running | done | failed | skipped
    current_step    TEXT,                   -- last step id attempted
    step_results    TEXT,                   -- JSON: { "step_id": { "status": "done", "output": "...", "duration_ms": 123 } }
    error           TEXT,                   -- last error message if failed
    attempts        INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(workflow_name, file_hash)
);

CREATE TABLE workflow_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_name   TEXT NOT NULL,
    started_at      DATETIME,
    finished_at     DATETIME,
    files_found     INTEGER DEFAULT 0,
    files_processed INTEGER DEFAULT 0,
    files_skipped   INTEGER DEFAULT 0,     -- already done
    files_failed    INTEGER DEFAULT 0
);
```

### How it works

1. Watcher finds a file matching `watch.extensions`
2. Compute blake3 hash of the file
3. Check `processed_files` for `(workflow_name, file_hash)`:
   - `status = done` → **skip** (already processed)
   - `status = failed` and `attempts < max_retries` → **retry** from `current_step`
   - `status = running` → **skip** (in progress, possible other worker)
   - not found → **insert** with `status = pending`
4. Execute flow steps, updating `current_step` and `step_results` after each
5. On completion set `status = done`, on unrecoverable failure set `status = failed`

### CLI state commands

```bash
mediaflow status                          # show all workflows, file counts by status
mediaflow status video-pipeline           # show files for specific workflow
mediaflow retry video-pipeline            # retry all failed files
mediaflow retry video-pipeline --file-hash abc123  # retry specific file
mediaflow reset video-pipeline            # clear all state, reprocess everything
mediaflow reset video-pipeline --status failed     # clear only failed
```

## Testing Strategy

### Unit tests

Pure logic, no external dependencies. Mock pyfilesystem2 with `fs.memoryfs.MemoryFS` and docker calls with `unittest.mock`.

What to test:
- YAML loading + env var interpolation
- Pydantic schema validation (valid specs, invalid specs, missing connections, bad presets)
- Template rendering (`{{file.name}}`, `{{file.stem}}`, nested contexts)
- Condition evaluation (`{{transcode.failed}}`, `{{file.size > 1000000}}`)
- State transitions (pending → running → done, retry logic)
- Extension filtering and glob matching

### Integration tests

Run with real services via docker-compose. CI spins up:
- **MinIO** — S3-compatible, test bucket auto-created
- **vsftpd** — FTP server with test user and seeded files
- **The app itself** — with test workflow specs mounted

What to test:
- Copy local → S3, S3 → local, FTP → local, cross-connection copy
- Full pipeline: watch dir → detect file → run all steps → verify output on S3
- Idempotency: run twice, second run skips everything
- Failure + retry: kill step mid-run, verify resume from correct step
- Watcher: drop a file into watched dir, assert pipeline triggers

### Test fixtures

Don't commit real media files. Generate them in CI:
```bash
# 1-second black video with audio tone
ffmpeg -f lavfi -i color=c=black:s=320x240:d=1 -f lavfi -i sine=f=440:d=1 -shortest fixtures/sample_video.mp4
# 1x1 red pixel
convert -size 1x1 xc:red fixtures/sample_image.jpg
```

### Devcontainer (`.devcontainer/`)

For local development. `docker-compose.yml` runs MinIO + vsftpd alongside the dev container. Dev container has ffmpeg, docker CLI (docker-in-docker), Python 3.12+, and all dev deps pre-installed.

```jsonc
// .devcontainer/devcontainer.json
{
  "name": "mediaflow-dev",
  "dockerComposeFile": "docker-compose.yml",
  "service": "app",
  "workspaceFolder": "/workspace",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },
  "postCreateCommand": "pip install -e '.[dev]'"
}
```

```yaml
# .devcontainer/docker-compose.yml
services:
  app:
    build:
      context: ..
      dockerfile: .devcontainer/Dockerfile
    volumes:
      - ..:/workspace:cached
    environment:
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - FTP_HOST=ftp
      - FTP_USER=testuser
      - FTP_PASS=testpass

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin

  ftp:
    image: fauria/vsftpd
    environment:
      FTP_USER: testuser
      FTP_PASS: testpass
      PASV_ADDRESS: ftp
    ports:
      - "21:21"
```

## CI / GitHub Workflows

### ci.yml — runs on every PR and push to main

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: ruff format --check src/ tests/
      - run: mypy src/mediaflow --strict

  unit:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit -v --cov=mediaflow --cov-report=xml
      - uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

### integration.yml — runs on push to main and release PRs

```yaml
name: Integration Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      minio:
        image: minio/minio
        ports:
          - 9000:9000
        env:
          MINIO_ROOT_USER: minioadmin
          MINIO_ROOT_PASSWORD: minioadmin
        options: >-
          --health-cmd "curl -f http://localhost:9000/minio/health/live"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 3
        # minio needs `server /data` — use a custom entrypoint or init container

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Generate test fixtures
        run: |
          mkdir -p tests/fixtures
          ffmpeg -f lavfi -i color=c=black:s=320x240:d=1 -f lavfi -i sine=f=440:d=1 -shortest tests/fixtures/sample_video.mp4
          ffmpeg -f lavfi -i color=c=red:s=100x100:d=1 -frames:v 1 tests/fixtures/sample_image.jpg

      - name: Create MinIO test bucket
        run: |
          pip install minio
          python -c "
          from minio import Minio
          c = Minio('localhost:9000', 'minioadmin', 'minioadmin', secure=False)
          if not c.bucket_exists('test-bucket'): c.make_bucket('test-bucket')
          "

      - run: pip install -e ".[dev]"

      - name: Run integration tests
        env:
          MINIO_ENDPOINT: http://localhost:9000
          MINIO_ACCESS_KEY: minioadmin
          MINIO_SECRET_KEY: minioadmin
          S3_TEST_BUCKET: test-bucket
        run: pytest tests/integration -v --timeout=120
```

### release.yml — semantic-release + DockerHub + PyPI

Uses [python-semantic-release](https://github.com/python-semantic-release/python-semantic-release) for automatic versioning based on conventional commits.

```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write
  id-token: write

jobs:
  release:
    runs-on: ubuntu-latest
    concurrency: release

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GH_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Semantic Release
        id: release
        uses: python-semantic-release/python-semantic-release@v9
        with:
          github_token: ${{ secrets.GH_TOKEN }}

      - name: Build package
        if: steps.release.outputs.released == 'true'
        run: |
          pip install build
          python -m build

      - name: Publish to PyPI
        if: steps.release.outputs.released == 'true'
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_TOKEN }}

      - name: Set up Docker Buildx
        if: steps.release.outputs.released == 'true'
        uses: docker/setup-buildx-action@v3

      - name: Login to DockerHub
        if: steps.release.outputs.released == 'true'
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push Docker image
        if: steps.release.outputs.released == 'true'
        uses: docker/build-push-action@v5
        with:
          push: true
          context: .
          tags: |
            ${{ secrets.DOCKERHUB_USERNAME }}/mediaflow:${{ steps.release.outputs.version }}
            ${{ secrets.DOCKERHUB_USERNAME }}/mediaflow:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Semantic release config

```json
// .releaserc.json
{
  "branch": "main",
  "version_toml": ["pyproject.toml:project.version"],
  "commit_parser": "angular",
  "major_on_zero": false,
  "tag_format": "v{version}",
  "changelog": {
    "changelog_file": "CHANGELOG.md"
  }
}
```

Commit convention:
- `feat: add upscale action` → minor bump (0.1.0 → 0.2.0)
- `fix: handle empty S3 prefix` → patch bump (0.1.0 → 0.1.1)
- `feat!: redesign connection config` or body with `BREAKING CHANGE:` → major bump
- `chore:`, `docs:`, `ci:` → no release

## pyproject.toml

```toml
[project]
name = "mediaflow"
version = "0.1.0"
description = "Spec-driven media pipeline CLI"
requires-python = ">=3.12"
license = { text = "MIT" }

dependencies = [
    "typer>=0.12",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "fs>=2.4",                     # pyfilesystem2
    "fs-s3fs>=1.1",                # S3 backend
    "fs.sshfs>=1.0",               # SFTP backend
    "structlog>=24.0",
    "blake3>=0.4",
    "docker>=7.0",                 # docker SDK for container management
    "jinja2>=3.1",                 # template rendering
    "httpx>=0.27",                 # async HTTP for callbacks
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-timeout>=2.3",
    "ruff>=0.5",
    "mypy>=1.10",
    "minio>=7.2",                  # for integration test setup
]

[project.scripts]
mediaflow = "mediaflow.cli:app"

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: requires external services (minio, ftp)",
]

[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
branch = "main"
commit_parser = "angular"
major_on_zero = false
tag_format = "v{version}"

[tool.semantic_release.changelog]
changelog_file = "CHANGELOG.md"

[build-system]
requires = ["setuptools>=68", "setuptools-scm>=8"]
build-backend = "setuptools.backends._legacy:_Backend"
```

## Production Dockerfile

```dockerfile
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# default state db location inside container
ENV MEDIAFLOW_STATE_DB=/data/state.db
# workflows mount point
ENV MEDIAFLOW_WORKFLOWS_DIR=/workflows

VOLUME ["/data", "/workflows", "/work"]

ENTRYPOINT ["mediaflow"]
CMD ["run", "--workflows-dir", "/workflows"]
```

Usage:
```bash
docker run -d \
  -v ./workflows:/workflows \
  -v ./work:/work \
  -v mediaflow-state:/data \
  -e S3_KEY=... \
  -e S3_SECRET=... \
  yourname/mediaflow:latest
```

## Key Design Decisions

### Action execution: local vs Docker

Every built-in action (transcode, hls, thumbnail, etc.) has two execution paths:
1. **Local** — if the binary exists on the host (e.g. `ffmpeg` is installed), run it directly via subprocess
2. **Docker** — if the binary is missing, pull the action's Docker image and run in a container with input/output volumes mounted

Detection is automatic: `shutil.which("ffmpeg")` → found? run locally. Not found? pull `mediaflow/ffmpeg:latest`.

The `docker` and `shell` actions are explicit overrides for custom commands.

### Template context

Each step has access to a context dict that grows as the pipeline progresses:

```python
{
    "file": {
        "name": "video.mov",           # original filename
        "stem": "video",               # without extension
        "ext": ".mov",                 # extension
        "size": 1048576,               # bytes
        "hash": "abc123...",           # blake3
    },
    "env": { ... },                     # all env vars
    "steps": {
        "transcode": {
            "status": "done",           # done | failed | skipped
            "output": "/work/video.mp4",
            "duration_ms": 12340,
        },
        "hls": { ... },
    }
}
```

Conditions like `if: {{steps.transcode.status == 'failed'}}` are evaluated against this context.

### Error handling per step

```yaml
- id: transcode
  action: transcode
  preset: h265-fast
  on_failure: retry       # retry | skip | abort (default: abort)
  max_retries: 3
  retry_delay: 30s        # wait between retries
```

`abort` = stop pipeline for this file, mark as failed.
`skip` = mark step as skipped, continue to next step.
`retry` = retry up to `max_retries` times with `retry_delay`.

## Actions Catalog — Full Reference

Every built-in action, its config keys, and ffmpeg/tool mapping.

### Video Actions

| Action | Description | Key Config | Tool |
|---|---|---|---|
| `video.info` | Probe codec, resolution, fps, duration, HDR, bitrate | `streams: [video, audio, subtitle]` | ffprobe |
| `video.crop` | Aspect ratio crop or auto black-bar detection | `mode: auto \| ratio`, `ratio: "16:9"`, `detect_threshold: 24` | ffmpeg `-vf cropdetect/crop` |
| `video.transcode` | Encode with preset (CPU or GPU) | `preset: h265-fast \| h264-web \| nvenc-h264 \| nvenc-h265 \| h265-10bit`, `crf: 18`, `hw: auto` | ffmpeg |
| `video.hls` | Multi-variant HLS packaging | `variants: [{h: 360, vbr: 600k, abr: 96k}, ...]`, `segment_time: 6`, `playlist_type: vod`, `tier_playlists: {free: [360,480,720], premium: [360,480,720,1080]}` | ffmpeg `-f hls` |
| `video.upscale` | AI anime upscale with fallback chain | `engine: dandere2x \| realesrgan \| lanczos`, `scale: 2`, `gpu: true`, `fallback: lanczos` | docker (dandere2x/realesrgan) or ffmpeg |
| `video.thumbnail` | Extract frame(s) as image | `mode: single \| grid \| sprite`, `at: "50%"`, `grid: "4x4"`, `width: 320` | ffmpeg `-ss -frames:v 1` |
| `video.preview` | Short animated preview for hover | `format: gif \| webp`, `duration: 3s`, `fps: 10`, `width: 480` | ffmpeg |
| `video.extract_audio` | Demux audio stream from container | `stream: 0`, `codec: copy \| aac \| flac` | ffmpeg `-map 0:a` |
| `video.extract_subs` | Extract subtitle tracks | `format: srt \| ass \| vtt`, `stream: all \| 0` | ffmpeg `-map 0:s` |
| `video.concat` | Concatenate segments | `mode: demuxer \| filter`, `inputs: [{{steps.*.output}}]` | ffmpeg `-f concat` |
| `video.normalize_audio` | 2-pass EBU R128 loudnorm on video's audio | `target_i: -16`, `target_tp: -1.5`, `target_lra: 11` | ffmpeg `loudnorm` |

### Audio Actions

| Action | Description | Key Config | Tool |
|---|---|---|---|
| `audio.info` | Probe codec, bitrate, sample rate, channels, duration | `—` | ffprobe |
| `audio.normalize` | EBU R128 2-pass loudnorm | `target_i: -16`, `target_tp: -1.5`, `target_lra: 11`, `linear: true` | ffmpeg `loudnorm` |
| `audio.convert` | Transcode to target codec | `codec: aac \| mp3 \| flac \| ogg \| opus \| wav \| alac`, `bitrate: 256k`, `sample_rate: 44100` | ffmpeg |
| `audio.hls` | Audio-only HLS packaging | `variants: [{bitrate: 128k}, {bitrate: 256k}]`, `segment_time: 10` | ffmpeg `-f hls` |
| `audio.tag` | Write/overwrite metadata tags | `tags: {title: "...", artist: "...", album: "..."}`, `strip_existing: false` | ffmpeg metadata or mutagen |
| `audio.embed_art` | Embed cover image into audio file | `image: "{{steps.thumbnail.output}}"`, `resize: 500x500` | ffmpeg `-i cover.jpg -map 0:a -map 1:v` |
| `audio.duration_check` | Compare input vs output duration | `tolerance_ms: 500`, `on_mismatch: warn \| fail` | ffprobe |

### Image Actions

| Action | Description | Key Config | Tool |
|---|---|---|---|
| `image.info` | Read dimensions, format, colorspace, pixel count | `—` | imagemagick `identify` or Pillow |
| `image.convert` | Format conversion | `format: jpeg \| png \| webp \| avif \| jxl`, `quality: 85` | imagemagick/Pillow |
| `image.resize` | Scale to target dimensions | `width: 1200`, `height: auto`, `filter: lanczos \| catmullrom`, `fit: contain \| cover \| fill` | imagemagick/Pillow |
| `image.crop` | Crop borders or manual rect | `mode: auto \| manual`, `auto_color: white \| black \| detect`, `rect: {x,y,w,h}` | imagemagick `-trim` or Pillow |
| `image.optimize` | Lossy/lossless compression | `engine: mozjpeg \| pngquant \| cjxl \| cavif \| oxipng`, `quality: 80`, `lossless: false` | mozjpeg/pngquant/etc. |
| `image.flip_rotate` | Flip or rotate | `flip: horizontal \| vertical \| none`, `rotate: 0 \| 90 \| 180 \| 270 \| exif-auto` | imagemagick/Pillow |
| `image.orientation_check` | Conditional: landscape/portrait/square | `expect: landscape \| portrait \| square` | imagemagick/Pillow |
| `image.pixel_check` | Conditional: total pixels above/below threshold | `min_pixels: 1000000`, `max_pixels: 50000000` | imagemagick/Pillow |
| `image.upscale` | AI upscale for manga/cover art | `engine: realesrgan \| waifu2x`, `scale: 2 \| 4`, `denoise: 1` | docker (realesrgan/waifu2x) |

### Utility Actions

| Action | Description | Key Config | Tool |
|---|---|---|---|
| `copy` | Cross-filesystem copy | `from: "{{file.path}}"`, `to: "s3://bucket/..."` | pyfilesystem2 |
| `move` | Copy + delete source | same as copy | pyfilesystem2 |
| `delete` | Remove file from any connection | `path: "{{file.path}}"` | pyfilesystem2 |
| `watermark` | Overlay image or text | `type: image \| text`, `position: bottom-right`, `opacity: 0.3`, `image: /assets/logo.png` | ffmpeg (video) or imagemagick (image) |
| `strip_metadata` | Remove EXIF/XMP/ID3 metadata | `keep: [orientation]`, `tool: exiftool \| ffmpeg` | exiftool/ffmpeg |
| `ocr` | Extract text from image | `lang: eng+jpn`, `psm: 6` | tesseract |
| `hash_verify` | Generate or verify checksum | `algo: blake3 \| sha256 \| md5`, `mode: generate \| verify`, `expected: "..."` | blake3/hashlib |
| `shell` | Run arbitrary shell command | `command: "..."`, `args: [...]`, `timeout: 300` | subprocess |
| `docker` | Run arbitrary container | `image: "..."`, `command: "..."`, `gpu: false`, `volumes: {}` | docker SDK |
| `http.post` | Webhook / API callback | `url: "..."`, `body: {}`, `headers: {}` | httpx |
| `http.get` | Fetch remote resource | `url: "..."`, `save_to: "..."` | httpx |

---

## FantasyS Workflow Specs (reference for `workflows/`)

Example workflow specs that replicate the existing FileFlows scripts as MediaFlow YAML.

### `workflows/video-pipeline.yaml` — Full video pipeline (mirrors `video-full-pipeline-hls.js`)

```yaml
name: video-pipeline
description: "Crop 4:3→16:9, anime upscale, normalize audio, multi-bitrate HLS with free/premium playlists"

connections:
  local:
    type: local
  output:
    type: s3
    bucket: "{{env.S3_BUCKET}}"
    prefix: hls-output/video/

watch:
  connection: local
  path: /media/incoming/video
  extensions: [.mp4, .mkv, .mov, .avi, .webm]
  poll_interval: 30s

flow:
  - id: probe
    action: video.info
    input: "{{file.path}}"

  - id: crop
    action: video.crop
    input: "{{file.path}}"
    mode: ratio
    ratio: "16:9"
    codec: libx264
    crf: 16
    preset: fast

  - id: upscale
    action: video.upscale
    input: "{{steps.crop.output}}"
    engine: dandere2x
    fallback: lanczos
    scale: 2
    gpu: true
    on_failure: skip       # fall back to lanczos in transcode step

  - id: normalize
    action: video.normalize_audio
    input: "{{file.path}}"
    target_i: -16
    target_tp: -1.5
    target_lra: 11

  - id: process
    action: transcode
    input: "{{steps.upscale.output if steps.upscale.status == 'done' else steps.crop.output}}"
    audio_input: "{{steps.normalize.output}}"
    preset: h264-web
    crf: 18
    scale: "1920:1080"
    scale_flags: lanczos
    audio_codec: aac
    audio_bitrate: 192k

  - id: hls
    action: video.hls
    input: "{{steps.process.output}}"
    variants:
      - { height: 360, video_bitrate: 600k, audio_bitrate: 96k }
      - { height: 480, video_bitrate: 1000k, audio_bitrate: 128k }
      - { height: 720, video_bitrate: 2500k, audio_bitrate: 192k }
      - { height: 1080, video_bitrate: 5000k, audio_bitrate: 256k }
    segment_time: 6
    tier_playlists:
      premium: [360, 480, 720, 1080]   # master.m3u8
      free: [360, 480, 720]            # free.m3u8

  - id: thumbnail
    action: video.thumbnail
    input: "{{steps.process.output}}"
    mode: sprite
    grid: "5x5"
    width: 320
    at: "10%"

  - id: preview
    action: video.preview
    input: "{{steps.process.output}}"
    format: webp
    duration: 3s
    fps: 10
    width: 480

  - id: upload
    action: copy
    from: "{{steps.hls.output_dir}}"
    to: "output://{{file.stem}}/"

  - id: notify
    action: http.post
    url: "{{env.BACKEND_URL}}/api/internal/media/video/{{file.stem}}/ready"
    body:
      hls_path: "{{file.stem}}/master.m3u8"
      free_path: "{{file.stem}}/free.m3u8"
      thumbnail: "{{steps.thumbnail.output}}"
      preview: "{{steps.preview.output}}"
      duration: "{{steps.probe.duration}}"
      upscaled: "{{steps.upscale.status == 'done'}}"
```

### `workflows/audio-pipeline.yaml` — ASMR pipeline (mirrors `audio-normalize-hls.js`)

```yaml
name: audio-pipeline
description: "Normalize audio (2-pass loudnorm), embed cover art, multi-bitrate HLS (128k/256k)"

connections:
  local:
    type: local
  output:
    type: s3
    bucket: "{{env.S3_BUCKET}}"
    prefix: hls-output/audio/

watch:
  connection: local
  path: /media/incoming/audio
  extensions: [.mp3, .flac, .wav, .m4a, .ogg, .opus]
  poll_interval: 30s

flow:
  - id: probe
    action: audio.info
    input: "{{file.path}}"

  - id: normalize
    action: audio.normalize
    input: "{{file.path}}"
    target_i: -16
    target_tp: -1.5
    target_lra: 11
    linear: true
    output_codec: aac
    output_bitrate: 256k

  - id: duration_check
    action: audio.duration_check
    original: "{{file.path}}"
    processed: "{{steps.normalize.output}}"
    tolerance_ms: 500
    on_mismatch: warn

  - id: hls
    action: audio.hls
    input: "{{steps.normalize.output}}"
    variants:
      - { bitrate: 128k }
      - { bitrate: 256k }
    segment_time: 10

  - id: upload
    action: copy
    from: "{{steps.hls.output_dir}}"
    to: "output://{{file.stem}}/"

  - id: notify
    action: http.post
    url: "{{env.BACKEND_URL}}/api/internal/media/audio/{{file.stem}}/ready"
    body:
      hls_path: "{{file.stem}}/master.m3u8"
      duration: "{{steps.probe.duration}}"
```

### `workflows/manga-process.yaml` — Manga/Pornhwa image pipeline

```yaml
name: manga-process
description: "Auto-crop borders, upscale, optimize to WebP/AVIF, generate thumbnails for manga/pornhwa pages"

connections:
  local:
    type: local
  output:
    type: s3
    bucket: "{{env.S3_BUCKET}}"
    prefix: images/manga/

watch:
  connection: local
  path: /media/incoming/manga
  extensions: [.jpg, .jpeg, .png, .webp, .bmp, .tiff]
  poll_interval: 15s

flow:
  - id: info
    action: image.info
    input: "{{file.path}}"

  - id: pixel_guard
    action: image.pixel_check
    input: "{{file.path}}"
    min_pixels: 10000         # skip corrupt/tiny images
    on_failure: abort

  - id: crop
    action: image.crop
    input: "{{file.path}}"
    mode: auto
    auto_color: detect        # detect white or black borders

  - id: upscale
    action: image.upscale
    input: "{{steps.crop.output}}"
    engine: realesrgan
    scale: 2
    denoise: 1
    if: "{{steps.info.width < 1200}}"   # only upscale small pages
    on_failure: skip

  - id: optimize_webp
    action: image.optimize
    input: "{{steps.upscale.output or steps.crop.output}}"
    engine: cwebp
    format: webp
    quality: 85

  - id: optimize_avif
    action: image.optimize
    input: "{{steps.upscale.output or steps.crop.output}}"
    engine: cavif
    format: avif
    quality: 70

  - id: thumbnail
    action: image.resize
    input: "{{steps.optimize_webp.output}}"
    width: 400
    height: auto
    filter: lanczos

  - id: strip
    action: strip_metadata
    input: "{{steps.optimize_webp.output}}"

  - id: upload_webp
    action: copy
    from: "{{steps.optimize_webp.output}}"
    to: "output://{{file.stem}}/page.webp"

  - id: upload_avif
    action: copy
    from: "{{steps.optimize_avif.output}}"
    to: "output://{{file.stem}}/page.avif"

  - id: upload_thumb
    action: copy
    from: "{{steps.thumbnail.output}}"
    to: "output://{{file.stem}}/thumb.webp"

  - id: notify
    action: http.post
    url: "{{env.BACKEND_URL}}/api/internal/media/page/{{file.stem}}/ready"
    body:
      webp: "{{file.stem}}/page.webp"
      avif: "{{file.stem}}/page.avif"
      thumbnail: "{{file.stem}}/thumb.webp"
      width: "{{steps.info.width}}"
      height: "{{steps.info.height}}"
      orientation: "{{steps.info.orientation}}"
```

---

## MVP Scope (v0.1.0)

What ships first:
- [ ] YAML spec loading + validation (pydantic)
- [ ] Connections: `local` and `s3` only
- [ ] Actions: `copy`, `move`, `delete`, `video.info`, `video.crop`, `transcode`, `video.hls`, `video.normalize_audio`, `thumbnail`, `shell`, `docker`, `http.post`
- [ ] Watcher: polling-based with extension filter
- [ ] State: SQLite persistence with idempotency
- [ ] CLI: `mediaflow run`, `mediaflow status`, `mediaflow retry`, `mediaflow reset`
- [ ] CI: lint, unit tests, integration tests with MinIO
- [ ] Release: semantic-release → PyPI + DockerHub

v0.2.0 — Audio:
- [ ] `audio.info`, `audio.normalize`, `audio.convert`, `audio.hls`, `audio.duration_check`
- [ ] `audio.tag`, `audio.embed_art`

v0.3.0 — Image:
- [ ] `image.info`, `image.convert`, `image.resize`, `image.crop`, `image.optimize`
- [ ] `image.upscale` (Real-ESRGAN / waifu2x docker)
- [ ] `image.orientation_check`, `image.pixel_check`, `image.flip_rotate`

v0.4.0 — Advanced:
- [ ] FTP/SFTP connections
- [ ] `video.upscale` (Dandere2x docker), `video.preview`, `video.extract_audio`, `video.extract_subs`
- [ ] `watermark`, `strip_metadata`, `ocr`, `hash_verify`
- [ ] GPU passthrough for docker actions

v1.0.0:
- [ ] Parallel step execution (DAG-based flow)
- [ ] Web UI for run visualization
- [ ] Server mode with distributed workers