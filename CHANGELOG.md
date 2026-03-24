# CHANGELOG


## v0.5.2 (2026-03-24)

### Bug Fixes

- Use twine for PyPI publish instead of trusted publishing
  ([`49414a9`](https://github.com/Rey092/mediariver/commit/49414a91dde50398c022db19afeaef3d8e50f13d))

Trusted publishing doesn't support reusable workflows. Use PYPI_TOKEN secret with twine upload
  instead.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>


## v0.5.1 (2026-03-24)

### Bug Fixes

- Add error logging to server thread for debugging crashes
  ([`8704823`](https://github.com/Rey092/mediariver/commit/8704823557632d8619f772b15c1fe40aeb91fd19))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Correct GitHub URLs in installer and README, fix pip install path
  ([`9736ad4`](https://github.com/Rey092/mediariver/commit/9736ad4fe7166a9809bc5aeb4625f38f54ad9e50))

- Replace placeholder user/mediariver with Rey092/mediariver - Fix pip install to run from repo
  directory (Push-Location) - Add setuptools<81 install for pkg_resources compatibility

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Installer error handling — check git exit code, verify pyproject.toml exists
  ([`3b6f85b`](https://github.com/Rey092/mediariver/commit/3b6f85bac9fe529a87307fcaff30552ac6e4bdea))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Update local shit
  ([`3313249`](https://github.com/Rey092/mediariver/commit/3313249b4fc9253ad12eaaf4425802970857904b))

- Use GITHUB_TOKEN instead of GH_TOKEN for semantic-release
  ([`cca6437`](https://github.com/Rey092/mediariver/commit/cca6437874b4a91d87626a99897eb0eaf7f264b4))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Continuous Integration

- Add CD + publish workflows, fix gitignore blocking .github/
  ([`6ee78b5`](https://github.com/Rey092/mediariver/commit/6ee78b55100cdcdfe67cf03fecaf1dbc45393364))

release.yml: semantic-release on push to main, triggers publish on new version publish.yml: PyPI +
  Docker CPU + Docker GPU (parallel)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>


## v0.5.0 (2026-03-24)

### Bug Fixes

- Configure structlog for tests to avoid colorama closed file errors on Windows
  ([`adc76ea`](https://github.com/Rey092/mediariver/commit/adc76ea987c10f64714ded98d7b052356cb90479))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Multiple CLI and copy action bugs found during demo testing
  ([`af4be6d`](https://github.com/Rey092/mediariver/commit/af4be6d61b9764916da124fedfcceb5caac206a2))

- copy/move actions now support absolute paths from step outputs (previously only connection URIs
  worked, breaking cross-step copies) - Loader resolves {{env.X}} in connection configs at YAML load
  time - CLI watcher resolves absolute system paths via fs.getsyspath() - Fix reset command: use
  synchronize_session="fetch" for reliable deletes - Fix DB path: normalize with .resolve() to avoid
  mixed separators on Windows - Add poll debug logging (poll_complete, is_known_hit)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Resolve lint issues and configure ruff rules
  ([`f6c9a23`](https://github.com/Rey092/mediariver/commit/f6c9a239226eea6367e86910a26f8e50a42ea2f6))

- Fix contextlib.suppress usage in CLI - Fix unused variable in executor test - Fix line-too-long in
  video action test - Update ruff config: remove TCH rules, ignore B008/B017/B023/N818

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Chores

- Add .gitignore and remove cached/build artifacts from tracking
  ([`2f11980`](https://github.com/Rey092/mediariver/commit/2f11980de15b824bfbdca23c9cc800c6199b18fd))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Documentation

- Add desktop app implementation plan (8 tasks)
  ([`c83ad94`](https://github.com/Rey092/mediariver/commit/c83ad9448503de7c62f23aca9c7c8d80ae7bf503))

Config, service, updater, FastAPI server, templates, tray app, installer scripts, README + release.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add MediaRiver design spec
  ([`f16d149`](https://github.com/Rey092/mediariver/commit/f16d149bce9f8bc1052e77ea5570a52df79acd39))

Comprehensive design document covering architecture decisions, workflow YAML schema, engine
  execution flow, action system, state management, and version roadmap through v0.4.0.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add MediaRiver Desktop design spec
  ([`1e08b82`](https://github.com/Rey092/mediariver/commit/1e08b827c857bfd8d9ee4a3754392fea3aa295e5))

Windows tray app + web UI + installer for managing the media pipeline. pystray + FastAPI +
  Jinja2/HTMX, git-based updates, Task Scheduler startup.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add v0.1.0 implementation plan (23 tasks)
  ([`1412079`](https://github.com/Rey092/mediariver/commit/1412079edae59ad21ca104bde7906dc93489b896))

Comprehensive task-by-task plan covering project setup, config layer, engine (templates, context,
  runner, errors), connections, action system, video actions, utility actions, watcher, CLI, CI/CD
  pipelines.

Reviewed and fixed: field aliasing for Python reserved words (if, from), resolved_input propagation
  to actions, context injection for connections and work_dir, build backend config, retry delay
  implementation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Fix desktop spec (review issues — Windows signals, SmartScreen, SQLite WAL)
  ([`f419c69`](https://github.com/Rey092/mediariver/commit/f419c69925fe122a7e1066ed00de510bab9d3c7c))

- C1: Use CTRL_BREAK_EVENT instead of SIGTERM for Windows subprocess shutdown - C2: Stop engine
  before git pull, only pip install if pyproject.toml changed - C3: Replace PyInstaller .exe with
  PowerShell one-liner installer (avoids SmartScreen) - H1: Remove work_dir from config (engine
  manages it internally) - H2: Specify asyncio.Queue broadcast for SSE log streaming - H4: Add
  SQLite WAL mode + timeout for concurrent access - H5: Note to add desktop deps to pyproject.toml -
  Added: port-in-use check, desktop.log, watchdog, workflow YAML endpoint, pagination

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Fix spec review issues (critical + moderate)
  ([`dd5b7a1`](https://github.com/Rey092/mediariver/commit/dd5b7a10a6b24072a5a0775e7543db0dfd341b1f))

- Fix duration_ms inconsistency in template context example - Fix normalize step to use cropped
  output for A/V sync - Add Path Resolution section defining connection://path URI format - Clarify
  input field is optional for actions with custom sources - Define retry scope: step-level retries
  are ephemeral, attempts is file-level - Add step_results JSON schema documentation - Remove
  skipped from file-level statuses - Add condition evaluation semantics - Add Working Directory
  section for temp file strategy - Optimize watcher to check by file_path before computing hash -
  Add http.get to v0.1.0, clarify http.post is JSON-only - Add --log-level to CLI - Fix FTP optional
  dependency (built into fs>=2.4)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

### Features

- Add action base types and pipeline context management
  ([`ae6c41a`](https://github.com/Rey092/mediariver/commit/ae6c41a89d2eefd44d709824602e375bd7b5bab9))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add audio actions (info, normalize, convert)
  ([`25a5172`](https://github.com/Rey092/mediariver/commit/25a5172e435a9b7b197e33be769587b1fecf0abc))

Implements audio.info (ffprobe JSON parser), audio.normalize (2-pass EBU R128 loudnorm), and
  audio.convert (codec conversion with ffmpeg flag mapping). All actions follow the established
  video action patterns with Pydantic params, @register_action, and executor abstraction.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add audio.hls and audio.duration_check actions
  ([`5af2332`](https://github.com/Rey092/mediariver/commit/5af2332c3671aedc62ee87e9a136706c04c76b71))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add audio.tag and audio.embed_art actions
  ([`44383e5`](https://github.com/Rey092/mediariver/commit/44383e59248610151d6e9c2d3e4da61b08156a1d))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add CI/CD pipelines, Dockerfile, and semantic release config
  ([`c38f0c9`](https://github.com/Rey092/mediariver/commit/c38f0c94657450f72a55c1a8c5822fb3a60bb622))

- Add command executor with local/docker strategy switching
  ([`0c9e84a`](https://github.com/Rey092/mediariver/commit/0c9e84ad17eaf640e44469331ffda8afc4d540d4))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add connection registry with local and S3 builders
  ([`a993fc8`](https://github.com/Rey092/mediariver/commit/a993fc88c2a58659d856f09d52b2d979e78b2bb0))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add cross-field workflow validation
  ([`f95be8b`](https://github.com/Rey092/mediariver/commit/f95be8bdb64b48e442469bf962c14d3852401363))

- Add decorator-based action registry
  ([`fea49be`](https://github.com/Rey092/mediariver/commit/fea49be5f2111fbc34be0ed669479eb47b787322))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add demo folder with sample files, workflows, and env config
  ([`1518c53`](https://github.com/Rey092/mediariver/commit/1518c53bc06da57c2d9eb0bea5459c4adf5d07d0))

- demo/.env with MinIO credentials - demo/workflows/ with video, audio, image demo workflows -
  demo/incoming/ with sample media files (generated + Big Buck Bunny clip) - Fix: resolve {{env.X}}
  templates in connection configs at YAML load time - Fix: resolve absolute system paths for local
  FS in CLI watcher

Usage: source demo/.env && mediariver run --workflows-dir demo/workflows

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add devcontainer with MinIO and S3 integration tests
  ([`c1be51a`](https://github.com/Rey092/mediariver/commit/c1be51a00e3353c87db089334db28c0cce01cb19))

- .devcontainer with docker-compose (app + MinIO) - 7 integration tests: S3
  write/read/list/remove/getinfo + cross-connection copy (local↔S3) + URI resolution

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add directory watcher with polling and extension filtering
  ([`f601d82`](https://github.com/Rey092/mediariver/commit/f601d8269a38a47ba023cf370fcef8019949b066))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add Docker demo with docker-compose (mediariver + MinIO)
  ([`279749d`](https://github.com/Rey092/mediariver/commit/279749dd9920d810a1fd9e4fb83fdab8bc989914))

- demo/docker-compose.yml: mediariver + MinIO + bucket init - Dockerfile: pin setuptools<81 for
  pkg_resources compatibility with pyfilesystem2 - Workflows use env vars for root paths (works in
  both local and Docker) - Verified: both video files processed, transcoded, thumbnailed, and
  uploaded to MinIO S3

Usage: docker compose -f demo/docker-compose.yml up

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add example video pipeline workflow
  ([`209914a`](https://github.com/Rey092/mediariver/commit/209914aa6c55a4bd474ce4409fd5d2b8a2502a3f))

- Add filesystem actions (copy, move, delete)
  ([`2807ced`](https://github.com/Rey092/mediariver/commit/2807cedfe5b1bd06ddb732bd0c1b06b36549dd07))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add FTP and SFTP connection builders
  ([`7704138`](https://github.com/Rey092/mediariver/commit/770413817d4d81574d1be6d48839da8e647c1005))

Registers ftp (via pyfilesystem2 built-in FTPFS) and sftp (via optional fs.sshfs) builders in the
  connection registry, with corresponding unit tests and pyproject.toml optional dependency groups.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add GPU (NVENC) support for video transcode
  ([`1ff493c`](https://github.com/Rey092/mediariver/commit/1ff493ce453e600e59c8fd22064d49af3b89ea32))

- New presets: nvenc-h264, nvenc-h265, h265-10bit - hw param: "auto" (detect NVENC), "gpu" (force),
  "cpu" (force) - Auto-detection: probes ffmpeg -encoders for h264_nvenc - NVENC uses -cq instead of
  -crf, -preset p4 - hw=auto with h264-web preset auto-upgrades to h264_nvenc if available - Tests:
  CPU, NVENC preset, and auto-detection modes

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add GPU (NVIDIA CUDA) Docker image with NVENC support
  ([`964d88f`](https://github.com/Rey092/mediariver/commit/964d88fbc3b931c160c39b25e2d07fad8c1ceb0c))

- Multi-stage Dockerfile: 'base' (CPU-only) and 'gpu' (NVIDIA CUDA + NVENC) - GPU image based on
  nvidia/cuda:12.6.3-runtime-ubuntu24.04 with libnvidia-encode - Demo docker-compose uses GPU target
  with nvidia device reservation - Verified: h264_nvenc encoding works inside container with --gpus
  all

Build: docker build --target gpu -t mediariver:gpu .

Run: docker run --gpus all mediariver:gpu

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Add image actions (crop, optimize, upscale)
  ([`0318ebb`](https://github.com/Rey092/mediariver/commit/0318ebb0f0e8861d0a24ef9a9a329f3c78489707))

Implements image.crop (auto-trim and manual rect via ImageMagick), image.optimize (multi-engine
  lossy/lossless compression), and image.upscale (AI upscaling via realesrgan/waifu2x with docker
  strategy).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add image actions (info, convert, resize)
  ([`53e5066`](https://github.com/Rey092/mediariver/commit/53e5066f2cd711ebec2718a0b32c2af061d83684))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add image actions (orientation_check, pixel_check, flip_rotate)
  ([`e58536d`](https://github.com/Rey092/mediariver/commit/e58536d8b088ff57ad45f528bb78f7e57d30ad83))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add Jinja2 template engine with condition evaluation
  ([`b8fabc8`](https://github.com/Rey092/mediariver/commit/b8fabc846725ac6981bb85755940f24f5617ffb5))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add pydantic schema models for workflow specs
  ([`dd54b95`](https://github.com/Rey092/mediariver/commit/dd54b95a3588bcdcb91314820aca2ef643f2eda8))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add sequential pipeline runner with condition evaluation and error handling
  ([`a85ed48`](https://github.com/Rey092/mediariver/commit/a85ed48b06d6067abad1b9aa8ebaea81f2211b2e))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add SQLAlchemy state models for file tracking
  ([`f5125fd`](https://github.com/Rey092/mediariver/commit/f5125fde41020f86ccd68f47e1b4f33d912cfe98))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add step error handling with retry/skip/abort strategies
  ([`cb26f00`](https://github.com/Rey092/mediariver/commit/cb26f00f81bdfbb85e330471044b6d840bf182d3))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add structlog logging configuration
  ([`1ee289a`](https://github.com/Rey092/mediariver/commit/1ee289abb73bf94573eb1282bd5b0fd59bf63e11))

- Add typer CLI with run, validate, status, retry, reset commands
  ([`158323c`](https://github.com/Rey092/mediariver/commit/158323c2c6bbd7d1d9bed4483c83f7ac8879d96b))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add utility actions (shell, docker, http.post, http.get)
  ([`3a8b8a6`](https://github.com/Rey092/mediariver/commit/3a8b8a6c39702fc3c5d0db567ee3ad5e4e150bc0))

- Add utility actions (watermark, strip_metadata, ocr, hash_verify)
  ([`a18b68e`](https://github.com/Rey092/mediariver/commit/a18b68e9979cd8441bdb7c25d3e59d18ac39a5f4))

Implements four new actions: watermark (image/text overlay via ffmpeg), strip_metadata (EXIF/XMP/ID3
  removal via ffmpeg or exiftool), ocr (Tesseract wrapper), and hash_verify (generate/verify
  blake3/sha256/md5 checksums using Python stdlib and blake3 library). All covered by TDD with 6 new
  unit tests (141 total passing).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add video actions (extract_subs, concat)
  ([`072f02c`](https://github.com/Rey092/mediariver/commit/072f02c5cdc04a98905f10eaed924752e24dfeca))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add video actions (info, crop, transcode, hls, normalize_audio, thumbnail)
  ([`0525015`](https://github.com/Rey092/mediariver/commit/052501597ceb8d3b3ed1dc1450797183f6bb21fc))

Implements 6 ffmpeg/ffprobe-backed video actions registered under the video.* namespace, with full
  unit test coverage using a mocked executor.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add video actions (upscale, preview, extract_audio)
  ([`fb15dba`](https://github.com/Rey092/mediariver/commit/fb15dbad2e4be0ddd53e6d7adc046438fb00d2ba))

Implements video.upscale (dandere2x/realesrgan/lanczos with fallback chain), video.preview (animated
  GIF/WebP hover thumbnails via ffmpeg), and video.extract_audio (audio demux with codec→ext
  mapping).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Add YAML workflow loader with directory scanning
  ([`6876b6a`](https://github.com/Rey092/mediariver/commit/6876b6a13e718a007be2a47509acfa3f4f5b1ee4))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Complete v0.2.0 — audio actions, example workflow, version bump
  ([`7c8870e`](https://github.com/Rey092/mediariver/commit/7c8870ed780c2bf783e23cde0d3d8947f80c57a6))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Complete v0.3.0 — image actions, manga workflow, version bump
  ([`ba2640c`](https://github.com/Rey092/mediariver/commit/ba2640c5e3a2250354af87552aecdf67ee6a2dff))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Complete v0.4.0 — advanced video, utility actions, FTP/SFTP, version bump
  ([`3c9a1dc`](https://github.com/Rey092/mediariver/commit/3c9a1dc89a45a4f74486b7ef41814df585768250))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Initialize mediariver project with dependencies
  ([`fe95253`](https://github.com/Rey092/mediariver/commit/fe95253cff7e900616318b719a6811d144d75fbc))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- Log hardware capabilities on startup (ffmpeg, GPU, docker)
  ([`9be7903`](https://github.com/Rey092/mediariver/commit/9be7903209cae90950368533efeeec0b87a04225))

Startup now shows: - mediariver version + loaded workflows + action count - ffmpeg path and version
  - GPU encoders detected (nvenc: av1, h264, hevc) - Docker availability and version

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- V0.5.0 — desktop app, README, release-ready
  ([`2fc6d2e`](https://github.com/Rey092/mediariver/commit/2fc6d2e48dcdee43b1f3189adf525dd96ef2c7b5))

- Bump version 0.4.0 → 0.5.0 in pyproject.toml and __init__.py - Add comprehensive README covering
  features, quick start, workflow example, action catalog, CLI reference, configuration, and
  development setup - Fix all ruff lint violations across src/ and tests/ (import sorting, unused
  imports, SIM105 contextlib.suppress refactors)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- Wire up action imports for registry auto-registration
  ([`9f6f275`](https://github.com/Rey092/mediariver/commit/9f6f27549d2b3fac7cc7b2fffd43a9d82818f805))

- **desktop**: Add config module and desktop dependencies
  ([`e070f25`](https://github.com/Rey092/mediariver/commit/e070f25dd694e0c43b294dec8e122301d2ed52f9))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **desktop**: Add engine service subprocess manager
  ([`20ebbf1`](https://github.com/Rey092/mediariver/commit/20ebbf121ea2dc077572ab3bb95355cb71df088e))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **desktop**: Add FastAPI web server with UI templates
  ([`aecb5d7`](https://github.com/Rey092/mediariver/commit/aecb5d79bd94211f0351b06d6d9eaa7499faa5ae))

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>

- **desktop**: Add git-based updater
  ([`2aa82d9`](https://github.com/Rey092/mediariver/commit/2aa82d97597d7cd306428495bd97d596beebf287))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

- **desktop**: Add PowerShell installer and uninstaller scripts
  ([`af5e66e`](https://github.com/Rey092/mediariver/commit/af5e66ebf4e1148e1b7a5664796f42eaa2738da4))

- **desktop**: Add tray app entry point with watchdog and auto-update
  ([`4ba9d1e`](https://github.com/Rey092/mediariver/commit/4ba9d1e2f8876f7b1b8c55a5f32431e854d06b96))

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

### Testing

- Add end-to-end workflow integration tests with S3
  ([`542b2ba`](https://github.com/Rey092/mediariver/commit/542b2badae5fa24f2a70b552f6b76b9f13b94a36))

- probe → copy to S3 (verifies file lands on MinIO) - probe → transcode → copy to S3 (real ffmpeg
  transcode) - state tracking (DB updated after pipeline run) - idempotency (done files skipped)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
