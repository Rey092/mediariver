# MediaRiver

Spec-driven media pipeline CLI — define workflows in YAML, process video, audio, and images at scale.

## Features

- **YAML-first** — workflows are plain files, Git-friendly and AI-friendly
- **38 built-in actions** — video, audio, image, and utility operations
- **GPU acceleration** — NVENC h264 / h265 / av1 via ffmpeg
- **Pluggable filesystems** — local, S3, FTP, SFTP (PyFilesystem2)
- **Docker-native** — auto-pulls container images when a local binary is absent
- **Idempotent** — SQLAlchemy state tracking; never reprocesses unless forced
- **Windows desktop app** — system-tray app with a local web UI

## Quick Start

**CLI**

```bash
pip install mediariver
mediariver validate --workflows-dir ./workflows
mediariver run --workflows-dir ./workflows
```

**Docker (GPU)**

```bash
docker run --gpus all -v ./workflows:/workflows -v ./media:/incoming mediariver:gpu
```

**Windows Desktop**

```powershell
irm https://raw.githubusercontent.com/user/mediariver/main/installer/bootstrap.ps1 | iex
```

## Workflow Example

```yaml
name: video-pipeline
connections:
  incoming:
    type: local
    path: /media/incoming
  storage:
    type: s3
    bucket: my-bucket
    prefix: processed/

watch:
  connection: incoming
  extensions: [.mp4, .mkv, .mov]
  poll_interval: 30s

steps:
  - name: probe
    action: video.info
    params:
      source: "{{ file.path }}"

  - name: transcode
    action: video.transcode
    params:
      source: "{{ file.path }}"
      dest: "{{ work_dir }}/output.mp4"
      preset: h264-web

  - name: upload
    action: copy
    params:
      src_connection: local
      src_path: "{{ work_dir }}/output.mp4"
      dst_connection: storage
      dst_path: "{{ file.stem }}.mp4"
```

## Action Catalog

### Video (13)

| Action | Description | Tool |
|--------|-------------|------|
| `video.info` | Extract codec, resolution, duration, bitrate, fps, HDR metadata | ffprobe |
| `video.transcode` | Encode with presets: h264-web, h265-fast, h265-10bit, nvenc-h264, nvenc-h265, nvenc-av1 | ffmpeg |
| `video.hls` | Multi-variant HLS packaging (360p–1080p + master playlist) | ffmpeg |
| `video.crop` | Aspect-ratio crop, letterbox removal, auto-detect black bars | ffmpeg |
| `video.upscale` | Anime upscale via Dandere2x (GPU), Real-ESRGAN, or Lanczos fallback | Docker |
| `video.thumbnail` | Frame extraction at timestamp; grid/sprite sheets for scrubbers | ffmpeg |
| `video.extract_audio` | Demux audio stream(s) from a video container | ffmpeg |
| `video.extract_subs` | Extract subtitle tracks (SRT / ASS / VTT) from MKV/MP4 | ffmpeg |
| `video.concat` | Concatenate video segments using demuxer or filter_complex | ffmpeg |
| `video.preview` | Generate short GIF/WebP hover-preview clip | ffmpeg |
| `video.normalize_audio` | In-place EBU R128 loudness normalisation on a video's audio track | ffmpeg |
| `video.watermark` | Overlay image or text on video | ffmpeg |
| `video.strip_metadata` | Remove EXIF/XMP/ID3 metadata from video container | ffmpeg |

### Audio (7)

| Action | Description | Tool |
|--------|-------------|------|
| `audio.info` | Extract codec, bitrate, sample rate, channels, duration | ffprobe |
| `audio.normalize` | EBU R128 2-pass loudnorm (I=−16, TP=−1.5, LRA=11) | ffmpeg |
| `audio.convert` | Convert between codecs: AAC, MP3, FLAC, OGG, WAV, OPUS | ffmpeg |
| `audio.hls` | Audio-only HLS packaging (128k/256k variants + master playlist) | ffmpeg |
| `audio.tag` | Write/rewrite ID3 or Vorbis metadata tags | mutagen |
| `audio.embed_art` | Embed cover art into audio file metadata | mutagen |
| `audio.duration_check` | Compare input vs output duration to detect truncation/corruption | ffprobe |

### Image (9)

| Action | Description | Tool |
|--------|-------------|------|
| `image.info` | Identify width, height, format, colorspace, pixel count | ImageMagick |
| `image.convert` | Convert between JPEG, PNG, WebP, AVIF, JXL | ImageMagick |
| `image.resize` | Resize/scale with configurable filter (lanczos, catmullrom) | ImageMagick |
| `image.crop` | Auto-crop white/black borders or manual crop rect | ImageMagick |
| `image.optimize` | Lossy/lossless compress via mozjpeg, pngquant, cjxl, cavif | varies |
| `image.flip_rotate` | Flip horizontal/vertical, rotate 90/180/270 or EXIF-auto | ImageMagick |
| `image.orientation_check` | Conditional: is landscape / portrait / square | built-in |
| `image.pixel_check` | Conditional: total pixels above/below threshold | built-in |
| `image.upscale` | Super-resolution upscale via Real-ESRGAN | Docker |

### Filesystem (3)

| Action | Description | Tool |
|--------|-------------|------|
| `copy` | Cross-filesystem file copy | PyFilesystem2 |
| `move` | Cross-filesystem file move (copy + delete) | PyFilesystem2 |
| `delete` | Remove a file from any configured connection | PyFilesystem2 |

### Utility (6)

| Action | Description | Tool |
|--------|-------------|------|
| `util.hash_verify` | Generate and verify BLAKE3 / MD5 / SHA256 checksums | blake3 |
| `util.strip_metadata` | Remove EXIF, XMP, ID3 metadata from any file type | exiftool |
| `util.ocr` | Extract text from images/frames via Tesseract | tesseract |
| `util.watermark` | Overlay image or text on an image | ImageMagick |
| `util.docker_run` | Run an arbitrary Docker container as a pipeline step | Docker |
| `util.shell` | Run an arbitrary shell command as a pipeline step | shell |

## CLI Commands

| Command | Description |
|---------|-------------|
| `mediariver run [NAME]` | Load workflows and start watching/processing (optional: run one workflow by name) |
| `mediariver validate` | Parse and validate all workflow specs without executing them |
| `mediariver status [NAME]` | Show processed-file counts grouped by status |
| `mediariver retry NAME` | Reset failed files to `pending` for reprocessing |
| `mediariver reset NAME` | Delete state records for a workflow (optionally filter by status) |

## Configuration

| Source | Details |
|--------|---------|
| `--workflows-dir` | Path to your `workflows/` directory (default: `./workflows`) |
| `--database-url` | SQLAlchemy URL (default: `sqlite:///$HOME/.mediariver/state.db`) |
| `MEDIARIVER_DB_URL` | Environment-variable override for the database URL |
| `config.json` | Optional file placed next to the binary (desktop app) |

Connection credentials (S3 keys, FTP passwords, SFTP keys) are read from environment variables referenced inside the YAML spec with `${ENV_VAR}` syntax.

## Development

```bash
git clone https://github.com/user/mediariver
cd mediariver
pip install -e ".[dev]"
pytest tests/unit/ -v
```

Run linting:

```bash
ruff check src/ tests/
```

## License

MIT
