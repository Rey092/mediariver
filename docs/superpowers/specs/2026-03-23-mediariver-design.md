# MediaRiver — Design Spec

## Overview

MediaRiver is a Python CLI that watches directories, picks up media files, and runs processing workflows defined in YAML specs. Think `docker-compose` but for media pipelines.

**Core principles:**
- YAML-first — workflows are specs in a `workflows/` folder, Git-friendly, AI-friendly
- Batteries included — ships with predefined actions for common media ops
- Pluggable filesystems — local, S3, FTP, SFTP via PyFilesystem2
- Docker-native — each action backed by a container image, auto-pulled if binary not available locally
- Idempotent — tracks processed files via SQLAlchemy, never reprocesses unless forced

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project name | `mediariver` | User decision |
| Action architecture | Monolithic registry (Approach A) | Simple, debuggable, easy to test. Registry pattern can evolve to plugin-based later |
| Local vs Docker execution | Explicit executor strategy (Approach B) | Separates execution concern from action logic. `CommandExecutor` handles local/docker switching. Testable via mock executor |
| Connection abstraction | Thin wrapper over PyFilesystem2 (Approach A) | FS API is already uniform across backends. Connection registry is a factory that returns FS objects |
| Template engine | Jinja2 (Approach A) | Already a dependency. Spec syntax is Jinja2-compatible. Handles expressions, conditions, fallbacks natively |
| State store | SQLAlchemy ORM | Works with SQLite now, Postgres later via connection string change. No custom ABC needed |
| Action params | `params` dict field | Action-specific config lives under `params`, not mixed with step-level fields (`id`, `action`, `input`, `if`, `on_failure`) |
| Implementation scope | v0.1.0 through v0.4.0 | v1.0.0 (DAG parallelism, web UI, distributed workers) considered in architecture but not implemented |

## Project Structure

```
mediariver/
├── src/mediariver/
│   ├── __init__.py
│   ├── __main__.py              # python -m mediariver
│   ├── cli.py                   # typer CLI (run, status, retry, reset, validate)
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py            # YAML parsing, env var interpolation
│   │   ├── schema.py            # Pydantic models for workflow specs
│   │   └── validators.py        # cross-field validation
│   ├── connections/
│   │   ├── __init__.py
│   │   ├── registry.py          # type string → FS builder
│   │   ├── local.py             # → OSFS
│   │   ├── s3.py                # → S3FS
│   │   ├── ftp.py               # → FTPFS (v0.4.0)
│   │   └── sftp.py              # → SSHFS (v0.4.0)
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── registry.py          # action name → class mapping
│   │   ├── base.py              # BaseAction ABC + ActionResult
│   │   ├── executor.py          # CommandExecutor (local/docker/auto)
│   │   ├── copy.py
│   │   ├── move.py
│   │   ├── delete.py
│   │   ├── video/
│   │   │   ├── __init__.py
│   │   │   ├── info.py          # video.info (ffprobe)
│   │   │   ├── crop.py          # video.crop
│   │   │   ├── transcode.py     # video.transcode
│   │   │   ├── hls.py           # video.hls
│   │   │   ├── normalize_audio.py  # video.normalize_audio
│   │   │   ├── thumbnail.py     # video.thumbnail
│   │   │   ├── upscale.py       # video.upscale (v0.4.0)
│   │   │   ├── preview.py       # video.preview (v0.4.0)
│   │   │   ├── extract_audio.py # video.extract_audio (v0.4.0)
│   │   │   ├── extract_subs.py  # video.extract_subs (v0.4.0)
│   │   │   └── concat.py        # video.concat (v0.4.0)
│   │   ├── audio/
│   │   │   ├── __init__.py
│   │   │   ├── info.py          # audio.info (v0.2.0)
│   │   │   ├── normalize.py     # audio.normalize (v0.2.0)
│   │   │   ├── convert.py       # audio.convert (v0.2.0)
│   │   │   ├── hls.py           # audio.hls (v0.2.0)
│   │   │   ├── duration_check.py # audio.duration_check (v0.2.0)
│   │   │   ├── tag.py           # audio.tag (v0.2.0)
│   │   │   └── embed_art.py     # audio.embed_art (v0.2.0)
│   │   ├── image/
│   │   │   ├── __init__.py
│   │   │   ├── info.py          # image.info (v0.3.0)
│   │   │   ├── convert.py       # image.convert (v0.3.0)
│   │   │   ├── resize.py        # image.resize (v0.3.0)
│   │   │   ├── crop.py          # image.crop (v0.3.0)
│   │   │   ├── optimize.py      # image.optimize (v0.3.0)
│   │   │   ├── upscale.py       # image.upscale (v0.3.0)
│   │   │   ├── orientation_check.py  # image.orientation_check (v0.3.0)
│   │   │   ├── pixel_check.py   # image.pixel_check (v0.3.0)
│   │   │   └── flip_rotate.py   # image.flip_rotate (v0.3.0)
│   │   └── util/
│   │       ├── __init__.py
│   │       ├── shell.py         # shell command execution
│   │       ├── docker_run.py    # arbitrary docker container
│   │       ├── http.py          # http.post, http.get
│   │       ├── watermark.py     # watermark (v0.4.0)
│   │       ├── strip_metadata.py # strip_metadata (v0.4.0)
│   │       ├── ocr.py           # ocr (v0.4.0)
│   │       └── hash_verify.py   # hash_verify (v0.4.0)
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── runner.py            # sequential step executor
│   │   ├── context.py           # builds/updates template context
│   │   ├── template.py          # Jinja2 resolver
│   │   └── errors.py            # retry/skip/abort logic
│   ├── watcher/
│   │   ├── __init__.py
│   │   ├── poller.py            # interval-based directory polling
│   │   └── filter.py            # extension/glob filtering
│   ├── state/
│   │   ├── __init__.py
│   │   ├── models.py            # SQLAlchemy models
│   │   └── database.py          # engine/session setup
│   ├── docker/
│   │   ├── __init__.py
│   │   └── manager.py           # pull, run, volume mount, cleanup
│   └── logging/
│       ├── __init__.py
│       └── setup.py             # structlog config
├── workflows/                   # example YAML specs
│   ├── video-pipeline.yaml
│   ├── audio-pipeline.yaml
│   └── manga-process.yaml
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .github/workflows/
│   ├── ci.yml
│   ├── integration.yml
│   └── release.yml
└── .releaserc.json
```

## Workflow YAML Schema

### Step-level fields (universal)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | yes | — | Unique step identifier |
| `action` | string | yes | — | Dotted action name from registry |
| `input` | string | no | — | Primary input path (Jinja2 template). Optional — some actions (e.g., `copy`, `http.post`) define their own source in `params` |
| `if` | string | no | — | Condition expression, skip if falsy |
| `on_failure` | enum | no | `abort` | `abort` / `skip` / `retry` |
| `max_retries` | int | no | `3` | Max retry attempts (only with `on_failure: retry`) |
| `retry_delay` | string | no | `30s` | Delay between retries |
| `params` | dict | no | `{}` | Action-specific config, validated by action's Pydantic model |

### Example workflow

```yaml
name: video-pipeline
description: "Crop, upscale, normalize, HLS"

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
    params:
      mode: ratio
      ratio: "16:9"
      codec: libx264
      crf: 16
      preset: fast

  - id: upscale
    action: video.upscale
    input: "{{steps.crop.output}}"
    on_failure: skip
    params:
      engine: dandere2x
      fallback: lanczos
      scale: 2
      gpu: true

  - id: normalize
    action: video.normalize_audio
    input: "{{steps.crop.output}}"   # use cropped video to keep audio in sync with video track
    params:
      target_i: -16
      target_tp: -1.5
      target_lra: 11

  - id: process
    action: video.transcode
    input: "{{steps.upscale.output if steps.upscale.status == 'done' else steps.crop.output}}"
    params:
      preset: h264-web
      crf: 18
      scale: "1920:1080"
      scale_flags: lanczos
      audio_input: "{{steps.normalize.output}}"
      audio_codec: aac
      audio_bitrate: 192k

  - id: hls
    action: video.hls
    input: "{{steps.process.output}}"
    params:
      variants:
        - { height: 360, video_bitrate: 600k, audio_bitrate: 96k }
        - { height: 480, video_bitrate: 1000k, audio_bitrate: 128k }
        - { height: 720, video_bitrate: 2500k, audio_bitrate: 192k }
        - { height: 1080, video_bitrate: 5000k, audio_bitrate: 256k }
      segment_time: 6
      tier_playlists:
        premium: [360, 480, 720, 1080]
        free: [360, 480, 720]

  - id: upload
    action: copy
    params:
      from: "{{steps.hls.output_dir}}"
      to: "output://{{file.stem}}/"

  - id: notify
    action: http.post
    params:
      url: "{{env.BACKEND_URL}}/api/internal/media/video/{{file.stem}}/ready"
      body:
        hls_path: "{{file.stem}}/master.m3u8"
        free_path: "{{file.stem}}/free.m3u8"
        duration: "{{steps.probe.duration}}"
```

## Engine & Execution Flow

### Runner

The runner processes a single file through a workflow's flow steps sequentially:

1. Watcher detects file matching `watch.extensions`
2. Compute blake3 hash
3. Check state DB:
   - `status = done` → skip (already processed)
   - `status = failed` and `attempts < max_retries` → retry from `current_step`
   - `status = running` → skip (in progress)
   - not found → insert as `pending`
4. For each step in `flow`:
   a. Evaluate `if` condition via Jinja2 → skip step if falsy
   b. Resolve `input` and all `params` values through Jinja2
   c. Validate resolved `params` against action's Pydantic `params_model`
   d. `action = ActionRegistry.get(step.action)`
   e. `result = action.run(context, resolved_params, executor)`
   f. Update context: `context.steps[step.id] = result`
   g. Update state DB: `current_step`, `step_results`
   h. On failure: apply `on_failure` strategy (abort/skip/retry)
5. Mark file as `done` or `failed`

### Template Context

Each step has access to a context dict that grows as the pipeline progresses:

```python
{
    "file": {
        "name": "video.mov",
        "stem": "video",
        "ext": ".mov",
        "size": 1048576,
        "hash": "abc123...",
        "path": "/media/incoming/video/video.mov",
    },
    "env": { ... },  # all env vars
    "steps": {
        "probe": {
            "status": "done",
            "output": "/tmp/probe.json",
            "width": 1920,
            "height": 1080,
            "duration": 120.5,      # seconds (float)
            "duration_ms": 120500,   # milliseconds (int)
        },
        "crop": {
            "status": "done",
            "output": "/tmp/video_cropped.mp4",
            "duration_ms": 3200,     # wall-clock time of the crop operation
        },
    }
}
```

### Condition Evaluation

The `if` field value is rendered as a Jinja2 template, producing a string. The engine evaluates the result as truthy/falsy: empty string, `"false"`, `"False"`, `"0"`, `"None"`, `""` are falsy; everything else is truthy. Example: `if: "{{steps.probe.width > 0}}"` renders to `"True"` or `"False"`.

### Error Handling

Each step declares its failure strategy:

- `abort` (default) — stop pipeline for this file, mark as `failed`
- `skip` — mark step as `skipped`, continue to next step. Context gets `status: "skipped"` and no `output`
- `retry` — retry up to `max_retries` times with `retry_delay` between attempts. Step-level retries are tracked ephemerally during the run (not persisted). The `attempts` field in `ProcessedFile` tracks file-level processing attempts (how many times the runner has picked up this file), used for the watcher's retry-from-`current_step` logic

## Action System

### BaseAction

```python
class BaseAction(ABC):
    name: str                          # e.g. "video.hls"
    params_model: type[BaseModel]      # Pydantic model for params validation

    @abstractmethod
    def run(self, context: dict, params: BaseModel, executor: CommandExecutor) -> ActionResult:
        ...

@dataclass
class ActionResult:
    status: str          # "done" | "failed" | "skipped"
    output: str | None   # primary output path
    duration_ms: int
    extras: dict         # action-specific data merged into step context
```

### Registry

Actions are registered via decorator:

```python
@register_action("video.crop")
class VideoCropAction(BaseAction):
    params_model = VideoCropParams
    ...
```

`ActionRegistry.get("video.crop")` returns the class. Unknown action name → fail at workflow load time.

### CommandExecutor

Handles the local/docker execution switching:

```python
executor.run(
    binary="ffmpeg",
    args=["-i", input, ...],
    docker_image="mediariver/ffmpeg:latest",
    volumes={"/tmp/work": "/work"},
    strategy="auto",  # auto | local | docker
)
```

- `auto`: `shutil.which(binary)` → found? `subprocess.run()`. Missing? Docker container.
- `local`: subprocess only, fail if binary missing
- `docker`: always use container

### Actions by Version

**v0.1.0:**
- `copy`, `move`, `delete` — cross-filesystem via PyFilesystem2
- `video.info` — ffprobe: codec, resolution, fps, duration, HDR, bitrate
- `video.crop` — aspect ratio crop or auto black-bar detection
- `video.transcode` — ffmpeg presets (h265-fast, h264-web, etc.)
- `video.hls` — multi-variant HLS with tier playlists
- `video.normalize_audio` — 2-pass EBU R128 loudnorm
- `video.thumbnail` — frame extraction, grid/sprite thumbnails
- `shell` — arbitrary shell command
- `docker` — arbitrary container execution
- `http.post` — webhook/API callback (JSON body only, no file upload)
- `http.get` — fetch remote resource, save to path

**v0.2.0:**
- `audio.info` — ffprobe: codec, bitrate, sample rate, channels, duration
- `audio.normalize` — EBU R128 2-pass loudnorm
- `audio.convert` — transcode between codecs (AAC, MP3, FLAC, OGG, OPUS, WAV, ALAC)
- `audio.hls` — audio-only HLS packaging (128k/256k variants)
- `audio.duration_check` — compare input vs output duration
- `audio.tag` — write/overwrite ID3/Vorbis metadata tags
- `audio.embed_art` — embed cover art into audio file

**v0.3.0:**
- `image.info` — dimensions, format, colorspace, pixel count
- `image.convert` — format conversion (JPEG, PNG, WebP, AVIF, JXL)
- `image.resize` — scale with configurable filter
- `image.crop` — auto-crop borders or manual rect
- `image.optimize` — lossy/lossless compression (mozjpeg, pngquant, cjxl, cavif)
- `image.upscale` — Real-ESRGAN / waifu2x via Docker
- `image.orientation_check` — conditional: landscape/portrait/square
- `image.pixel_check` — conditional: total pixels above/below threshold
- `image.flip_rotate` — flip horizontal/vertical, rotate 90/180/270/EXIF-auto

**v0.4.0:**
- FTP/SFTP connections
- `video.upscale` — Dandere2x (GPU, Docker), Real-ESRGAN fallback, lanczos last resort
- `video.preview` — short GIF/WebP preview clip
- `video.extract_audio` — demux audio stream
- `video.extract_subs` — extract subtitle tracks
- `video.concat` — concatenate video segments
- `watermark` — overlay image/text on video or image
- `strip_metadata` — exiftool/ffmpeg metadata strip
- `ocr` — tesseract wrapper
- `hash_verify` — blake3/md5/sha256 checksum
- GPU passthrough for Docker actions

## Connections

Factory registry — each connection type returns a PyFilesystem2 `FS` object:

```python
builders = {
    "local": build_local_fs,    # → OSFS(path)
    "s3": build_s3_fs,          # → S3FS(bucket, prefix, endpoint, key, secret)
    "ftp": build_ftp_fs,        # → FTPFS(host, user, passwd)        (v0.4.0)
    "sftp": build_sftp_fs,      # → SSHFS(host, user, passwd/key)    (v0.4.0)
}
```

Connection config from YAML is Jinja2-resolved (so `{{env.S3_BUCKET}}` works), then passed to the builder. Cross-connection copies use `fs.copy.copy_file()`.

### Path Resolution

Actions that accept filesystem paths (e.g., `copy`, `move`, `delete`) support a `connection://path` URI format:

- `output://videos/file.mp4` → resolves to the `output` connection's FS object at path `videos/file.mp4`
- `local:///media/incoming/video.mp4` → resolves to the `local` connection
- A bare path with no `://` prefix defaults to the `local` connection (or the workflow's `watch.connection` if no `local` connection is defined)

The URI is parsed by splitting on the first `://`. The left part is the connection name (looked up in the workflow's `connections` map), and the right part is the relative path within that FS. The `copy` action uses this to open source and destination FS objects and call `fs.copy.copy_file()` across them.

`input` at the step level is always a local filesystem path (the file being processed). Connection URIs are only used inside `params` for actions that explicitly support them.

## State (SQLAlchemy)

### Models

```python
class ProcessedFile(Base):
    __tablename__ = "processed_files"
    id: Mapped[int]                    # PK autoincrement
    workflow_name: Mapped[str]
    file_path: Mapped[str]
    file_hash: Mapped[str]             # blake3
    file_size: Mapped[int]
    status: Mapped[str]                # pending | running | done | failed
    current_step: Mapped[str | None]
    step_results: Mapped[dict]         # JSON column, shape: {"step_id": {"status": "done|failed|skipped", "output": "/path/...", "duration_ms": 123, "error": "...", ...}}
    error: Mapped[str | None]
    attempts: Mapped[int] = 0
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    # UniqueConstraint("workflow_name", "file_hash")

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[int]                    # PK autoincrement
    workflow_name: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    files_found: Mapped[int] = 0
    files_processed: Mapped[int] = 0
    files_skipped: Mapped[int] = 0
    files_failed: Mapped[int] = 0
```

Default: SQLite at `~/.mediariver/state.db`. Override via `--database-url` or `MEDIARIVER_DATABASE_URL` env var. Swap to Postgres by changing the URL.

## CLI

```
mediariver run [--workflows-dir PATH] [--database-url URL] [--log-level debug|info|warning|error]
    Load all YAML specs, validate, start watchers, run engine loop.

mediariver run <workflow-name>
    Run only the named workflow.

mediariver validate [--workflows-dir PATH]
    Load & validate all specs, report errors, exit. No execution.

mediariver status [workflow-name]
    Show file counts by status (pending/running/done/failed).

mediariver retry <workflow-name> [--file-hash HASH]
    Reset failed files to pending, re-run.

mediariver reset <workflow-name> [--status STATUS]
    Clear state (all or filtered by status).
```

## Working Directory

Each file run gets an isolated working directory for intermediate files:

- Location: `~/.mediariver/work/<workflow_name>/<file_hash>/`
- Override via `--work-dir` or `MEDIARIVER_WORK_DIR` env var
- Actions write intermediate outputs here (cropped video, normalized audio, etc.)
- Docker containers mount this directory as `/work`
- Cleanup policy: deleted on successful completion. Kept on failure for debugging. `mediariver reset` cleans up associated work dirs.

## Watcher

Polling-based directory watcher:

1. For each workflow, open the FS connection for `watch.connection`
2. List files in `watch.path`, filter by `watch.extensions`
3. For each matching file, check state DB by `(workflow_name, file_path)` as fast path — skip if already known
4. For new files, compute blake3 hash and check by `(workflow_name, file_hash)` — skip if already processed
5. Queue for processing
6. Sleep `watch.poll_interval`

Single-threaded per workflow in v0.1.0–v0.4.0. v1.0.0 adds worker pools.

## Docker Manager

```python
class DockerManager:
    def pull_if_missing(image: str) -> None
    def run(image, command, args, volumes, gpu=False, env=None) -> CompletedProcess
    def cleanup(container_id) -> None
```

Uses the `docker` Python SDK. Working temp dir auto-mounted to `/work` in container. GPU passthrough (`--gpus all`) available via action params (v0.4.0).

## Dependencies

```toml
[project]
name = "mediariver"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "typer>=0.12",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "fs>=2.4",
    "fs-s3fs>=1.1",
    "sqlalchemy>=2.0",
    "structlog>=24.0",
    "blake3>=0.4",
    "docker>=7.0",
    "jinja2>=3.1",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-timeout>=2.3",
    "ruff>=0.5",
    "mypy>=1.10",
    "minio>=7.2",
]
ftp = []                    # v0.4.0 — FTP is built into fs>=2.4
sftp = ["fs.sshfs>=1.0"]   # v0.4.0
```

## CI/CD

- **ci.yml** — every PR: ruff lint + format check, mypy strict, pytest unit tests with coverage
- **integration.yml** — push to main: MinIO service container, ffmpeg install, fixture generation, integration tests
- **release.yml** — push to main: python-semantic-release → PyPI + DockerHub

Conventional commits: `feat:` → minor, `fix:` → patch, `feat!:` / `BREAKING CHANGE:` → major.

## Future Considerations (v1.0.0, not implemented)

- DAG-based parallel step execution
- Web UI for run visualization
- Server mode with distributed workers (requires Postgres state store)
- Plugin-based action discovery via entry points
