# AI Subtitle Generation & Translation

## Overview

Add AI-powered subtitle generation and translation to MediaRiver. Introduces a thin AI provider abstraction with a single Gemini implementation, two new actions (`ai.subtitle`, `ai.translate_subtitle`), and a new `ai:` config section in workflow YAML.

## AI Provider Abstraction

New package `src/mediariver/ai/` with:

- `base.py` — abstract `AIProvider` with a `generate(prompt, files, config) -> str` method
- `registry.py` — `AIProviderRegistry` (same pattern as `ActionRegistry`)
- `gemini.py` — `GeminiProvider` using `google-genai` SDK

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
- Injected into `context["_ai"]` at runtime
- Actions look up their provider by name from the registry

### Schema Changes

```python
class AIProviderConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str

class WorkflowSpec(BaseModel):
    # ... existing fields ...
    ai: dict[str, AIProviderConfig] = {}
```

### Loader Changes

Resolve `{{env.X}}` in the `ai:` section at load time, same block as connections.

### Runner Changes

Set `context["_ai"]` from the resolved ai config before running steps.

## Action: `ai.subtitle`

**File:** `src/mediariver/actions/ai/subtitle.py`

Generates subtitles from audio or video files using an AI provider.

### Params

```python
class AISubtitleParams(BaseModel):
    provider: str = "gemini"
    language: str | None = None    # source language hint, auto-detect if None
    format: str = "vtt"            # output format (any pysubs2 format id)
```

### Behavior

1. Accepts audio or video file as input
2. Sends file to the AI provider with a prompt requesting:
   - Timestamped transcription as structured JSON (`start_ms`, `end_ms`, `text`)
   - Detected language as ISO 639-1 code
3. Parses response into `pysubs2.SSAFile` events
4. Saves in requested format via `pysubs2`
5. Returns `ActionResult` with:
   - `output`: path to subtitle file
   - `extras`: `language` (detected code), `format`, `line_count`

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
    target_language: str                # required, e.g. "en", "ja", "uk"
    source_language: str | None = None  # hint, auto-detect if None
    format: str | None = None           # output format, None = same as input
```

### Behavior

1. Loads subtitle file with `pysubs2` (any supported format)
2. Extracts text from events, preserving style tags separately
3. Batches lines (~50 per request) and sends to AI provider for translation
4. Replaces text in events with translations, styles and timing intact
5. Saves in requested format (or same as input if not specified)
6. Returns `ActionResult` with:
   - `output`: path to translated subtitle file
   - `extras`: `source_language`, `target_language`, `format`, `line_count`

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
