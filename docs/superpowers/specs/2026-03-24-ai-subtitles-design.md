# AI Subtitle Generation & Translation

## Overview

Add AI-powered subtitle generation and translation to MediaRiver. Introduces a thin AI provider abstraction with a single Gemini implementation, two new actions (`ai.subtitle`, `ai.translate_subtitle`), and a new `ai:` config section in workflow YAML.

## AI Provider Abstraction

New package `src/mediariver/ai/` with:

- `base.py` — abstract `AIProvider` base class
- `registry.py` — factory dict mapping provider names to builder functions (same pattern as `connections/registry.py`)
- `gemini.py` — `GeminiProvider` implementation using `google-genai` SDK

### Provider Interface

```python
class AIProvider(ABC):
    """Abstract base for AI providers."""

    @abstractmethod
    def generate(self, prompt: str, media: list[Path] | None = None) -> str:
        """Send a prompt with optional media files, return text response.

        Args:
            prompt: The text prompt.
            media: Optional list of file paths. The provider handles upload
                   (inline for small files, File API for large ones).

        Returns:
            Raw text response from the model.
        """
```

The `media` parameter is a list of `pathlib.Path` objects. The provider implementation is responsible for:
- Detecting MIME type from file extension
- Choosing inline vs File API upload based on file size (Gemini: inline < 20MB, File API for larger)
- Polling for upload completion on large files
- Cleaning up uploaded files after the request

### Provider Config (workflow YAML)

New optional top-level `ai:` section:

```yaml
ai:
  gemini:
    provider: gemini
    api_key: "{{env.GEMINI_API_KEY}}"
    model: gemini-3-pro
```

- `{{env.X}}` templates resolved at load time (same as connections)
- Injected into `context["_ai"]` as **instantiated `AIProvider` objects** (not raw config)
- Actions receive ready-to-use provider instances

### Schema Changes

```python
class AIProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str

class WorkflowSpec(BaseModel):
    # ... existing fields ...
    ai: dict[str, AIProviderConfig] = {}  # optional, workflows without AI omit this
```

Provider-specific fields (like `api_key`, `model`) pass through via `extra="allow"`. Each provider implementation validates its own required fields at instantiation time, raising clear errors for missing/invalid config.

### Registry (factory pattern)

Follows `connections/registry.py` — a plain dict of builder functions, not a decorator-based registry:

```python
_builders: dict[str, Callable] = {
    "gemini": build_gemini_provider,
}

def build_ai_provider(name: str, config: AIProviderConfig) -> AIProvider:
    if config.provider not in _builders:
        raise KeyError(f"Unknown AI provider: '{config.provider}'")
    return _builders[config.provider](name, config)
```

### Loader Changes

Resolve `{{env.X}}` in the `ai:` section at load time, same block as connections.

### Runner Changes

`PipelineRunner.__init__` gains an `ai_providers: dict[str, AIProvider] | None = None` parameter.

The application layer (where workflows are loaded and connections are built) also builds AI providers:

```python
# In the application bootstrap (alongside connection building):
ai_providers = {}
for name, ai_config in workflow.ai.items():
    ai_providers[name] = build_ai_provider(name, ai_config)

runner = PipelineRunner(workflow, executor, connections, work_dir, ai_providers=ai_providers)
```

In `run_file()`, before the step loop:
```python
context["_ai"] = self.ai_providers  # dict[str, AIProvider]
```

Actions retrieve their provider:
```python
provider = context["_ai"][params.provider]  # returns instantiated AIProvider
response = provider.generate(prompt, media=[input_path])
```

## Action: `ai.subtitle`

**File:** `src/mediariver/actions/ai/subtitle.py`

Generates subtitles from audio or video files using an AI provider.

### Params

```python
SUBTITLE_FORMATS = Literal["ass", "ssa", "srt", "vtt", "ttml", "sami", "microdvd", "mpl2", "tmp", "json"]

class AISubtitleParams(BaseModel):
    provider: str = "gemini"
    language: str | None = None              # source language hint, auto-detect if None
    format: SUBTITLE_FORMATS = "vtt"         # output format (pysubs2 format id)
```

### Behavior

1. Accepts audio or video file as input
2. Sends file to the AI provider with a prompt requesting structured JSON output:
   - Array of `{"start_ms": int, "end_ms": int, "text": str}` objects
   - A `"language"` field with ISO 639-1 code
3. Parses JSON response — validates each entry has required fields, discards malformed entries with a warning log
4. Builds `pysubs2.SSAFile` from valid entries
5. Saves in requested format via `pysubs2`
6. Returns `ActionResult` with:
   - `output`: path to subtitle file
   - `extras`: `language` (detected code), `format`, `line_count`

### Large file handling

Gemini has a ~20MB inline limit. The provider's `generate()` method handles this transparently via the File API. For very large video files, users should consider placing a `video.extract_audio` step before `ai.subtitle` to reduce upload size — this is a workflow-level optimization, not enforced by the action.

### Error handling

- If JSON parsing fails entirely: raise `RuntimeError` (action fails, respects `on_failure` policy)
- If individual entries are malformed: skip them, log warning, continue with valid entries
- If zero valid entries parsed: raise `RuntimeError`

### Workflow Usage

```yaml
- id: subtitle
  action: ai.subtitle
  input: "{{file.path}}"
  params:
    provider: gemini
    format: vtt
```

## Action: `ai.translate_subtitle`

**File:** `src/mediariver/actions/ai/translate_subtitle.py`

Translates subtitle files between languages. Supports all pysubs2 formats. Preserves timing and style tags.

### Params

```python
class AITranslateSubtitleParams(BaseModel):
    provider: str = "gemini"
    target_language: str                         # required, e.g. "en", "ja", "uk"
    source_language: str | None = None           # hint, auto-detect if None
    format: SUBTITLE_FORMATS | None = None       # output format, None = same as input
    batch_size: int = Field(default=50, ge=10, le=200)  # lines per API request
```

### Behavior

1. Loads subtitle file with `pysubs2` (any supported format)
2. Extracts text from events, preserving style tags (ASS/SSA override tags like `{\b1}`) separately
3. Batches lines by `batch_size` and sends plain text to AI provider for translation, with line numbers to maintain 1:1 mapping
4. Parses translated lines from response, replaces text in events — styles and timing intact
5. Saves in requested format (or same as input if not specified)
6. Returns `ActionResult` with:
   - `output`: path to translated subtitle file
   - `extras`: `source_language`, `target_language`, `format`, `line_count`

### Batching details

- Default 50 lines per batch, configurable via `batch_size` param
- If a batch fails: the action raises (fails the step). Partial translation is not saved — it's all or nothing per file to avoid half-translated output.
- The prompt includes line numbers (e.g., `1: Hello\n2: World`) and instructs the model to return the same numbered format, ensuring 1:1 line mapping even if the model wants to merge/split lines.

### Workflow Usage

```yaml
- id: translate
  action: ai.translate_subtitle
  input: "{{steps.subtitle.output}}"
  params:
    provider: gemini
    source_language: "{{steps.subtitle.language}}"
    target_language: en
    format: srt
```

## Note on Action Pattern

The AI actions make HTTP API calls rather than running CLI binaries. They still receive `executor: CommandExecutor` in `run()` (the runner passes it unconditionally) but do not use it. This is the first category of actions that are API-based rather than CLI-based. The `BaseAction` interface remains unchanged.

## New Dependencies

- `google-genai` — Google GenAI SDK for Gemini API
- `pysubs2` — subtitle parsing/writing (11 formats: ASS, SSA, SRT, VTT, TTML, SAMI, MicroDVD, MPL2, TMP, JSON, Whisper JAX)

## Supported Subtitle Formats (via pysubs2)

| Format | Extension | ID |
|--------|-----------|-----|
| SubStation Alpha v4+ | .ass | ass |
| SubStation Alpha | .ssa | ssa |
| SubRip | .srt | srt |
| WebVTT | .vtt | vtt |
| TTML | — | ttml |
| SAMI | — | sami |
| MicroDVD | .sub | microdvd |
| MPL2 | .txt | mpl2 |
| TMP | — | tmp |
| JSON | — | json |

## Full Workflow Example

```yaml
name: video-with-subtitles
description: "Transcode video, generate subtitles, translate to English"

ai:
  gemini:
    provider: gemini
    api_key: "{{env.GEMINI_API_KEY}}"
    model: gemini-3-pro

connections:
  local:
    type: local
    root: /media

watch:
  connection: local
  path: /incoming/video
  extensions: [.mp4, .mkv, .avi]
  poll_interval: 30s

flow:
  - id: probe
    action: video.info
    input: "{{file.path}}"

  - id: transcode
    action: video.transcode
    input: "{{file.path}}"
    params:
      preset: h264-web
      crf: 23

  - id: subtitle
    action: ai.subtitle
    input: "{{steps.transcode.output}}"
    params:
      provider: gemini
      format: vtt

  - id: translate_en
    action: ai.translate_subtitle
    input: "{{steps.subtitle.output}}"
    if: "{{steps.subtitle.language != 'en'}}"
    params:
      provider: gemini
      source_language: "{{steps.subtitle.language}}"
      target_language: en
      format: srt
```

## Files to Create

| File | Purpose |
|------|---------|
| `src/mediariver/ai/__init__.py` | Package init |
| `src/mediariver/ai/base.py` | Abstract AIProvider |
| `src/mediariver/ai/registry.py` | AIProviderRegistry |
| `src/mediariver/ai/gemini.py` | GeminiProvider implementation |
| `src/mediariver/actions/ai/__init__.py` | AI actions package init |
| `src/mediariver/actions/ai/subtitle.py` | ai.subtitle action |
| `src/mediariver/actions/ai/translate_subtitle.py` | ai.translate_subtitle action |

## Files to Modify

| File | Change |
|------|--------|
| `src/mediariver/config/schema.py` | Add `AIProviderConfig`, add `ai` field to `WorkflowSpec` |
| `src/mediariver/config/loader.py` | Resolve env templates in `ai:` section |
| `src/mediariver/engine/runner.py` | Inject `context["_ai"]` |
| `src/mediariver/actions/__init__.py` | Import new AI actions |
| `pyproject.toml` | Add `google-genai` and `pysubs2` dependencies |
