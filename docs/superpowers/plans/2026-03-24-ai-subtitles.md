# AI Subtitle Generation & Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-powered subtitle generation and translation to MediaRiver via a new AI provider abstraction and two new actions.

**Architecture:** A thin `ai/` package provides an abstract provider interface with a factory registry (matching the connections pattern). A single Gemini implementation uses the `google-genai` SDK. Two new actions (`ai.subtitle`, `ai.translate_subtitle`) use the provider for transcription and translation, with `pysubs2` for subtitle format handling.

**Tech Stack:** Python 3.12, google-genai SDK, pysubs2, Pydantic v2, structlog

---

## File Map

### New files

| File | Responsibility |
|------|----------------|
| `src/mediariver/ai/__init__.py` | Package init, re-exports `AIProvider`, `build_ai_provider` |
| `src/mediariver/ai/base.py` | Abstract `AIProvider` class |
| `src/mediariver/ai/registry.py` | Factory dict + `build_ai_provider()` function |
| `src/mediariver/ai/gemini.py` | `GeminiProvider` — wraps google-genai SDK |
| `src/mediariver/actions/ai/__init__.py` | AI actions package init, shared `SUBTITLE_FORMATS` Literal |
| `src/mediariver/actions/ai/subtitle.py` | `ai.subtitle` action |
| `src/mediariver/actions/ai/translate_subtitle.py` | `ai.translate_subtitle` action |
| `tests/unit/test_ai_provider.py` | Tests for provider abstraction + registry |
| `tests/unit/test_ai_gemini.py` | Tests for GeminiProvider (mocked SDK) |
| `tests/unit/test_actions_ai.py` | Tests for ai.subtitle and ai.translate_subtitle actions |
| `tests/fixtures/workflows/valid_ai.yaml` | Fixture workflow with `ai:` section |
| `tests/fixtures/subtitles/sample.vtt` | Fixture subtitle file for translation tests |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml:8-21` | Add `google-genai` and `pysubs2` to dependencies |
| `src/mediariver/config/schema.py:1-58` | Add `AIProviderConfig` model, add `ai` field to `WorkflowSpec` |
| `src/mediariver/config/loader.py:14-31` | Resolve `{{env.X}}` in `ai:` section |
| `src/mediariver/engine/runner.py:22-35,43-46` | Accept `ai_providers` param, inject into context |
| `src/mediariver/actions/__init__.py:1-53` | Import new AI action modules |
| `src/mediariver/cli.py:74-132` | Build AI providers alongside connections, pass to runner |

---

### Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml:8-21`

- [ ] **Step 1: Add google-genai and pysubs2 to dependencies**

In `pyproject.toml`, add to the `dependencies` list:

```toml
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
    "setuptools<81",
    "google-genai>=1.0",
    "pysubs2>=1.7",
]
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: Successful install with google-genai and pysubs2 resolved

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add google-genai and pysubs2 dependencies"
```

---

### Task 2: Schema — add AIProviderConfig and ai field

**Files:**
- Modify: `src/mediariver/config/schema.py:1-58`
- Test: `tests/unit/test_schema.py`

- [ ] **Step 1: Write failing tests for AIProviderConfig and WorkflowSpec.ai**

Add to `tests/unit/test_schema.py`:

```python
from mediariver.config.schema import AIProviderConfig

class TestAIProviderConfig:
    def test_valid_gemini_config(self):
        config = AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")
        assert config.provider == "gemini"
        assert config.api_key == "test-key"

    def test_extra_fields_allowed(self):
        config = AIProviderConfig(provider="gemini", api_key="k", model="m", temperature=0.5)
        assert config.temperature == 0.5

    def test_provider_required(self):
        with pytest.raises(ValidationError):
            AIProviderConfig()


class TestWorkflowSpecAI:
    def test_workflow_without_ai_section(self):
        """ai section is optional — existing workflows should still work."""
        spec = WorkflowSpec(
            name="no-ai",
            connections={"local": ConnectionConfig(type="local")},
            watch=WatchConfig(connection="local", path="/tmp", extensions=[".mp4"]),
            flow=[StepConfig(id="probe", action="video.info", input="{{file.path}}")],
        )
        assert spec.ai == {}

    def test_workflow_with_ai_section(self):
        spec = WorkflowSpec(
            name="with-ai",
            connections={"local": ConnectionConfig(type="local")},
            watch=WatchConfig(connection="local", path="/tmp", extensions=[".mp4"]),
            flow=[StepConfig(id="probe", action="video.info", input="{{file.path}}")],
            ai={"gemini": AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")},
        )
        assert "gemini" in spec.ai
        assert spec.ai["gemini"].provider == "gemini"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_schema.py::TestAIProviderConfig tests/unit/test_schema.py::TestWorkflowSpecAI -v`
Expected: FAIL — `AIProviderConfig` does not exist yet

- [ ] **Step 3: Implement schema changes**

In `src/mediariver/config/schema.py`, add `AIProviderConfig` after `ConnectionConfig` and add `ai` field to `WorkflowSpec`:

```python
class AIProviderConfig(BaseModel):
    """Configuration for an AI provider."""

    model_config = ConfigDict(extra="allow")

    provider: str


class WorkflowSpec(BaseModel):
    """Top-level workflow specification."""

    name: str
    description: str = ""
    connections: dict[str, ConnectionConfig]
    watch: WatchConfig
    flow: list[StepConfig]
    ai: dict[str, AIProviderConfig] = {}

    # ... existing validator unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_schema.py -v`
Expected: All PASS (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/mediariver/config/schema.py tests/unit/test_schema.py
git commit -m "feat: add AIProviderConfig to workflow schema"
```

---

### Task 3: Loader — resolve env templates in ai section

**Files:**
- Modify: `src/mediariver/config/loader.py:14-31`
- Create: `tests/fixtures/workflows/valid_ai.yaml`
- Test: `tests/unit/test_loader.py`

- [ ] **Step 1: Create fixture workflow with ai section**

Create `tests/fixtures/workflows/valid_ai.yaml`:

```yaml
name: test-ai
description: "Workflow with AI provider"

ai:
  gemini:
    provider: gemini
    api_key: "{{env.TEST_GEMINI_KEY}}"
    model: gemini-3-pro

connections:
  local:
    type: local

watch:
  connection: local
  path: /tmp/incoming
  extensions: [.mp4]

flow:
  - id: subtitle
    action: ai.subtitle
    input: "{{file.path}}"
    params:
      provider: gemini
      format: vtt
```

- [ ] **Step 2: Write failing test for ai env resolution**

Add to `tests/unit/test_loader.py`:

```python
import os

class TestLoadWorkflowAI:
    def test_load_workflow_with_ai_section(self):
        spec = load_workflow(FIXTURES_DIR / "valid_ai.yaml")
        assert "gemini" in spec.ai
        assert spec.ai["gemini"].provider == "gemini"

    def test_ai_env_templates_resolved(self, monkeypatch):
        monkeypatch.setenv("TEST_GEMINI_KEY", "resolved-key-123")
        spec = load_workflow(FIXTURES_DIR / "valid_ai.yaml")
        assert spec.ai["gemini"].api_key == "resolved-key-123"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_loader.py::TestLoadWorkflowAI -v`
Expected: FAIL — `api_key` still contains `{{env.TEST_GEMINI_KEY}}`

- [ ] **Step 4: Implement loader changes**

In `src/mediariver/config/loader.py`, in `load_workflow()`, add after the connections resolution block:

```python
    # Resolve env templates in AI provider configs
    if "ai" in raw and isinstance(raw["ai"], dict):
        for ai_name, ai_data in raw["ai"].items():
            if isinstance(ai_data, dict):
                raw["ai"][ai_name] = resolve_value(ai_data, env_ctx)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_loader.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mediariver/config/loader.py tests/fixtures/workflows/valid_ai.yaml tests/unit/test_loader.py
git commit -m "feat: resolve env templates in workflow ai section"
```

---

### Task 4: AI provider abstraction — base + registry

**Files:**
- Create: `src/mediariver/ai/__init__.py`
- Create: `src/mediariver/ai/base.py`
- Create: `src/mediariver/ai/registry.py`
- Test: `tests/unit/test_ai_provider.py`

- [ ] **Step 1: Write failing tests for AIProvider base and registry**

Create `tests/unit/test_ai_provider.py`:

```python
"""Tests for AI provider abstraction and registry."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mediariver.ai.base import AIProvider
from mediariver.ai.registry import build_ai_provider, _builders
from mediariver.config.schema import AIProviderConfig


class TestAIProviderBase:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            AIProvider()

    def test_subclass_must_implement_generate(self):
        class IncompleteProvider(AIProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_works(self):
        class FakeProvider(AIProvider):
            def generate(self, prompt, media=None):
                return "fake response"

        provider = FakeProvider()
        assert provider.generate("hello") == "fake response"


class TestAIProviderRegistry:
    def test_build_unknown_provider_raises(self):
        config = AIProviderConfig(provider="nonexistent")
        with pytest.raises(KeyError, match="Unknown AI provider"):
            build_ai_provider("test", config)

    def test_gemini_in_builders(self):
        assert "gemini" in _builders
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ai_provider.py -v`
Expected: FAIL — modules don't exist

- [ ] **Step 3: Implement base.py**

Create `src/mediariver/ai/base.py`:

```python
"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


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

- [ ] **Step 4: Implement registry.py**

Create `src/mediariver/ai/registry.py`:

```python
"""AI provider factory registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mediariver.ai.base import AIProvider
    from mediariver.config.schema import AIProviderConfig


def _build_gemini(name: str, config: AIProviderConfig) -> AIProvider:
    from mediariver.ai.gemini import GeminiProvider

    return GeminiProvider(name, config)


_builders: dict[str, Callable[..., AIProvider]] = {
    "gemini": _build_gemini,
}


def build_ai_provider(name: str, config: AIProviderConfig) -> AIProvider:
    """Build an AI provider instance from config."""
    if config.provider not in _builders:
        raise KeyError(
            f"Unknown AI provider: '{config.provider}'. Available: {list(_builders.keys())}"
        )
    return _builders[config.provider](name, config)
```

- [ ] **Step 5: Create __init__.py**

Create `src/mediariver/ai/__init__.py`:

```python
"""AI provider abstraction."""

from mediariver.ai.base import AIProvider
from mediariver.ai.registry import build_ai_provider

__all__ = ["AIProvider", "build_ai_provider"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/unit/test_ai_provider.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mediariver/ai/ tests/unit/test_ai_provider.py
git commit -m "feat: add AI provider abstraction with factory registry"
```

---

### Task 5: GeminiProvider implementation

**Files:**
- Create: `src/mediariver/ai/gemini.py`
- Test: `tests/unit/test_ai_gemini.py`

- [ ] **Step 1: Write failing tests for GeminiProvider**

Create `tests/unit/test_ai_gemini.py`:

```python
"""Tests for GeminiProvider."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mediariver.ai.gemini import GeminiProvider
from mediariver.config.schema import AIProviderConfig


class TestGeminiProviderInit:
    @patch("mediariver.ai.gemini.genai")
    def test_requires_api_key(self, mock_genai):
        config = AIProviderConfig(provider="gemini", model="gemini-3-pro")
        with pytest.raises(ValueError, match="api_key"):
            GeminiProvider("test", config)

    @patch("mediariver.ai.gemini.genai")
    def test_default_model(self, mock_genai):
        config = AIProviderConfig(provider="gemini", api_key="test-key")
        provider = GeminiProvider("test", config)
        assert provider.model == "gemini-2.5-flash"

    @patch("mediariver.ai.gemini.genai")
    def test_custom_model(self, mock_genai):
        config = AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")
        provider = GeminiProvider("test", config)
        assert provider.model == "gemini-3-pro"


class TestGeminiProviderGenerate:
    @patch("mediariver.ai.gemini.genai")
    def test_generate_text_only(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = "generated text"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        config = AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")
        provider = GeminiProvider("test", config)
        result = provider.generate("hello")

        assert result == "generated text"
        mock_client.models.generate_content.assert_called_once()

    @patch("mediariver.ai.gemini.genai")
    def test_generate_with_media_small_file(self, mock_genai, tmp_path):
        """Files under 20MB should be sent inline."""
        mock_response = MagicMock()
        mock_response.text = "transcription"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client

        small_file = tmp_path / "audio.mp3"
        small_file.write_bytes(b"x" * 1000)

        config = AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")
        provider = GeminiProvider("test", config)
        result = provider.generate("transcribe", media=[small_file])

        assert result == "transcription"

    @patch("mediariver.ai.gemini.genai")
    @patch("mediariver.ai.gemini.INLINE_SIZE_LIMIT", 50)
    def test_generate_with_media_large_file(self, mock_genai, tmp_path):
        """Files over the inline limit should use the File API."""
        mock_response = MagicMock()
        mock_response.text = "transcription"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_upload = MagicMock()
        mock_upload.state.name = "ACTIVE"
        mock_client.files.upload.return_value = mock_upload
        mock_genai.Client.return_value = mock_client

        # Create a file larger than the patched limit (50 bytes)
        large_file = tmp_path / "video.mp4"
        large_file.write_bytes(b"x" * 100)

        config = AIProviderConfig(provider="gemini", api_key="test-key", model="gemini-3-pro")
        provider = GeminiProvider("test", config)
        result = provider.generate("transcribe", media=[large_file])

        assert result == "transcription"
        mock_client.files.upload.assert_called_once()
        mock_client.files.delete.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ai_gemini.py -v`
Expected: FAIL — `GeminiProvider` doesn't exist

- [ ] **Step 3: Implement GeminiProvider**

Create `src/mediariver/ai/gemini.py`:

```python
"""Gemini AI provider implementation."""

from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Any

import structlog
from google import genai

from mediariver.ai.base import AIProvider
from mediariver.config.schema import AIProviderConfig

log = structlog.get_logger()

INLINE_SIZE_LIMIT = 20 * 1024 * 1024  # 20MB


class GeminiProvider(AIProvider):
    """AI provider using Google Gemini via the google-genai SDK."""

    def __init__(self, name: str, config: AIProviderConfig) -> None:
        api_key = getattr(config, "api_key", None)
        if not api_key:
            raise ValueError(f"AI provider '{name}' requires 'api_key'")
        self.name = name
        self.model: str = getattr(config, "model", "gemini-2.5-flash")
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, media: list[Path] | None = None) -> str:
        """Send prompt with optional media files to Gemini."""
        contents: list[Any] = []
        uploaded_files: list[Any] = []

        if media:
            for path in media:
                part, uploaded = self._prepare_media(path)
                contents.append(part)
                if uploaded:
                    uploaded_files.append(uploaded)

        contents.append(prompt)

        log.info("gemini_generate", model=self.model, media_count=len(media or []))
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
            )
            return response.text
        finally:
            for f in uploaded_files:
                try:
                    self._client.files.delete(name=f.name)
                    log.debug("gemini_file_deleted", name=f.name)
                except Exception as e:
                    log.warning("gemini_file_delete_failed", name=f.name, error=str(e))

    def _prepare_media(self, path: Path) -> tuple[Any, Any]:
        """Prepare a media file for the API — inline or File API upload.

        Returns:
            Tuple of (content_part, uploaded_file_or_None).
            uploaded_file is set only for File API uploads (for cleanup).
        """
        mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        file_size = path.stat().st_size

        if file_size <= INLINE_SIZE_LIMIT:
            log.debug("gemini_inline_upload", path=str(path), size=file_size)
            part = genai.types.Part.from_bytes(
                data=path.read_bytes(),
                mime_type=mime_type,
            )
            return part, None

        log.info("gemini_file_api_upload", path=str(path), size=file_size)
        uploaded = self._client.files.upload(file=path, config={"mime_type": mime_type})

        # Poll until active
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = self._client.files.get(name=uploaded.name)

        if uploaded.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini file upload failed: state={uploaded.state.name}")

        return uploaded, uploaded
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_ai_gemini.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mediariver/ai/gemini.py tests/unit/test_ai_gemini.py
git commit -m "feat: implement GeminiProvider with inline and File API upload"
```

---

### Task 6: Runner — inject AI providers into context

**Files:**
- Modify: `src/mediariver/engine/runner.py:22-35,43-46`
- Test: `tests/unit/test_runner.py`

- [ ] **Step 1: Write failing test for ai_providers in context**

Add to `tests/unit/test_runner.py`:

```python
    def test_ai_providers_in_context(self, tmp_path):
        ActionRegistry.register("mock.action", MockAction)
        workflow = _make_workflow(
            [
                StepConfig(id="step1", action="mock.action"),
            ]
        )

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake")

        mock_ai = {"gemini": "fake_provider"}
        runner = PipelineRunner(workflow, executor=MagicMock(), ai_providers=mock_ai)
        runner.run_file(str(test_file), "fakehash")

        assert MockAction.last_context["_ai"] is mock_ai
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_runner.py::TestPipelineRunner::test_ai_providers_in_context -v`
Expected: FAIL — `PipelineRunner.__init__` doesn't accept `ai_providers`

- [ ] **Step 3: Implement runner changes**

In `src/mediariver/engine/runner.py`, update `PipelineRunner.__init__` to accept `ai_providers`:

```python
    def __init__(
        self,
        workflow: WorkflowSpec,
        executor: CommandExecutor,
        connections: dict[str, Any] | None = None,
        work_dir: str | None = None,
        ai_providers: dict[str, Any] | None = None,
    ) -> None:
        self.workflow = workflow
        self.executor = executor
        self.connections = connections or {}
        self.work_dir = work_dir or "/tmp"
        self.ai_providers = ai_providers or {}
```

In `run_file()`, add after `context["_work_dir"]`:

```python
        context["_ai"] = self.ai_providers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_runner.py -v`
Expected: All PASS (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/mediariver/engine/runner.py tests/unit/test_runner.py
git commit -m "feat: inject AI providers into pipeline context"
```

---

### Task 7: CLI — build AI providers and pass to runner

**Files:**
- Modify: `src/mediariver/cli.py:74-132`

- [ ] **Step 1: Update CLI to build AI providers**

In `src/mediariver/cli.py`, add import at the top of the `run` function (alongside the other lazy imports):

```python
    from mediariver.ai.registry import build_ai_provider
```

Inside the `for spec in specs:` loop, after the connections building block (after line 77), add:

```python
                ai_providers = {}
                for ai_name, ai_config in spec.ai.items():
                    ai_providers[ai_name] = build_ai_provider(ai_name, ai_config)
```

Update the `PipelineRunner` constructor call (around line 127) to pass `ai_providers`:

```python
                    runner = PipelineRunner(
                        spec,
                        executor,
                        connections=connections,
                        work_dir=str(work_dir),
                        ai_providers=ai_providers,
                    )
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/mediariver/cli.py
git commit -m "feat: build AI providers in CLI and pass to runner"
```

---

### Task 8: ai.subtitle action

**Files:**
- Create: `src/mediariver/actions/ai/__init__.py`
- Create: `src/mediariver/actions/ai/subtitle.py`
- Test: `tests/unit/test_actions_ai.py`

- [ ] **Step 1: Write failing tests for ai.subtitle**

Create `tests/unit/test_actions_ai.py`:

```python
"""Tests for AI actions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mediariver.actions.ai.subtitle import AISubtitleAction, AISubtitleParams
from mediariver.actions.base import ActionResult


class FakeProvider:
    def generate(self, prompt: str, media=None) -> str:
        return json.dumps({
            "language": "en",
            "subtitles": [
                {"start_ms": 0, "end_ms": 1000, "text": "Hello world"},
                {"start_ms": 1500, "end_ms": 3000, "text": "This is a test"},
            ],
        })


class TestAISubtitleParams:
    def test_defaults(self):
        params = AISubtitleParams()
        assert params.provider == "gemini"
        assert params.format == "vtt"
        assert params.language is None

    def test_invalid_format_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AISubtitleParams(format="invalid_format")


class TestAISubtitleAction:
    def _make_context(self, tmp_path: Path, ai_provider: Any) -> dict[str, Any]:
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"fake video content")
        return {
            "file": {"name": "test.mp4", "stem": "test", "ext": ".mp4", "path": str(test_file)},
            "_work_dir": str(tmp_path),
            "_ai": {"gemini": ai_provider},
        }

    def test_generates_vtt_subtitle(self, tmp_path):
        ctx = self._make_context(tmp_path, FakeProvider())
        params = AISubtitleParams(provider="gemini", format="vtt")
        action = AISubtitleAction()

        result = action.run(ctx, params, executor=MagicMock())

        assert result.status == "done"
        assert result.output.endswith(".vtt")
        assert Path(result.output).exists()
        assert result.extras["language"] == "en"
        assert result.extras["line_count"] == 2

    def test_generates_srt_subtitle(self, tmp_path):
        ctx = self._make_context(tmp_path, FakeProvider())
        params = AISubtitleParams(provider="gemini", format="srt")
        action = AISubtitleAction()

        result = action.run(ctx, params, executor=MagicMock())

        assert result.status == "done"
        assert result.output.endswith(".srt")

    def test_uses_resolved_input(self, tmp_path):
        alt_file = tmp_path / "alt.mp3"
        alt_file.write_bytes(b"fake audio")
        ctx = self._make_context(tmp_path, FakeProvider())
        params = AISubtitleParams(provider="gemini")
        action = AISubtitleAction()

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=str(alt_file))
        assert result.status == "done"

    def test_raises_on_invalid_json(self, tmp_path):
        class BadProvider:
            def generate(self, prompt, media=None):
                return "not json at all"

        ctx = self._make_context(tmp_path, BadProvider())
        params = AISubtitleParams(provider="gemini")
        action = AISubtitleAction()

        with pytest.raises(RuntimeError, match="Failed to parse"):
            action.run(ctx, params, executor=MagicMock())

    def test_raises_on_zero_valid_entries(self, tmp_path):
        class EmptyProvider:
            def generate(self, prompt, media=None):
                return json.dumps({"language": "en", "subtitles": []})

        ctx = self._make_context(tmp_path, EmptyProvider())
        params = AISubtitleParams(provider="gemini")
        action = AISubtitleAction()

        with pytest.raises(RuntimeError, match="No valid subtitle"):
            action.run(ctx, params, executor=MagicMock())

    def test_skips_malformed_entries(self, tmp_path):
        class PartialProvider:
            def generate(self, prompt, media=None):
                return json.dumps({
                    "language": "uk",
                    "subtitles": [
                        {"start_ms": 0, "end_ms": 1000, "text": "Good"},
                        {"start_ms": "bad", "end_ms": 2000, "text": "Bad timestamp"},
                        {"text": "Missing timestamps"},
                    ],
                })

        ctx = self._make_context(tmp_path, PartialProvider())
        params = AISubtitleParams(provider="gemini")
        action = AISubtitleAction()

        result = action.run(ctx, params, executor=MagicMock())
        assert result.extras["line_count"] == 1
        assert result.extras["language"] == "uk"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_actions_ai.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create the actions/ai package init**

Create `src/mediariver/actions/ai/__init__.py`:

```python
"""AI-powered actions."""

from typing import Literal

SUBTITLE_FORMATS = Literal[
    "ass", "ssa", "srt", "vtt", "ttml", "sami", "microdvd", "mpl2", "tmp", "json"
]
```

- [ ] **Step 4: Implement ai.subtitle action**

Create `src/mediariver/actions/ai/subtitle.py`:

```python
"""AI subtitle generation action — transcribe audio/video to subtitles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import pysubs2
import structlog
from pydantic import BaseModel

from mediariver.actions.ai import SUBTITLE_FORMATS
from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

log = structlog.get_logger()

TRANSCRIPTION_PROMPT = """\
Transcribe the audio from this media file with precise timestamps.

Return ONLY a JSON object with this exact structure:
{
  "language": "<ISO 639-1 code of the spoken language>",
  "subtitles": [
    {"start_ms": <int>, "end_ms": <int>, "text": "<subtitle line>"},
    ...
  ]
}

Rules:
- Timestamps are in milliseconds
- Each subtitle line should be 1-2 sentences, suitable for display
- Detect the spoken language and return its ISO 639-1 code (e.g., "en", "ja", "uk")
- Return ONLY valid JSON, no markdown fences or extra text
"""


class AISubtitleParams(BaseModel):
    provider: str = "gemini"
    language: str | None = None
    format: SUBTITLE_FORMATS = "vtt"


@register_action("ai.subtitle")
class AISubtitleAction(BaseAction):
    name = "ai.subtitle"
    params_model = AISubtitleParams

    def run(
        self,
        context: dict[str, Any],
        params: AISubtitleParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        provider = context["_ai"][params.provider]

        prompt = TRANSCRIPTION_PROMPT
        if params.language:
            prompt += f"\nThe spoken language is: {params.language}\n"

        response = provider.generate(prompt, media=[Path(input_path)])

        # Parse JSON response
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse AI response as JSON: {e}") from e

        language = data.get("language", "unknown")
        raw_subs = data.get("subtitles", [])

        # Build pysubs2 subtitle file
        subs = pysubs2.SSAFile()
        valid_count = 0

        for entry in raw_subs:
            try:
                start = int(entry["start_ms"])
                end = int(entry["end_ms"])
                text = str(entry["text"])
                subs.append(pysubs2.SSAEvent(start=start, end=end, text=text))
                valid_count += 1
            except (KeyError, ValueError, TypeError) as e:
                log.warning("subtitle_entry_skipped", error=str(e), entry=entry)

        if valid_count == 0:
            raise RuntimeError("No valid subtitle entries parsed from AI response")

        output_path = os.path.join(work_dir, f"{stem}.{params.format}")
        subs.save(output_path, format_=params.format)

        return ActionResult(
            status="done",
            output=output_path,
            extras={
                "language": language,
                "format": params.format,
                "line_count": valid_count,
            },
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_actions_ai.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mediariver/actions/ai/ tests/unit/test_actions_ai.py
git commit -m "feat: add ai.subtitle action for AI-powered transcription"
```

---

### Task 9: ai.translate_subtitle action

**Files:**
- Create: `src/mediariver/actions/ai/translate_subtitle.py`
- Create: `tests/fixtures/subtitles/sample.vtt`
- Test: `tests/unit/test_actions_ai.py` (append)

- [ ] **Step 1: Create fixture subtitle file**

Create `tests/fixtures/subtitles/sample.vtt`:

```
WEBVTT

00:00:00.000 --> 00:00:01.000
Привіт, світе

00:00:01.500 --> 00:00:03.000
Це тестові субтитри

00:00:04.000 --> 00:00:06.000
Третій рядок тексту
```

- [ ] **Step 2: Write failing tests for ai.translate_subtitle**

Append to `tests/unit/test_actions_ai.py`:

```python
import pysubs2

from mediariver.actions.ai.translate_subtitle import (
    AITranslateSubtitleAction,
    AITranslateSubtitleParams,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class FakeTranslateProvider:
    def generate(self, prompt: str, media=None) -> str:
        # Return numbered lines matching the input format
        return "1: Hello, world\n2: These are test subtitles\n3: Third line of text"


class TestAITranslateSubtitleParams:
    def test_target_language_required(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AITranslateSubtitleParams(provider="gemini")

    def test_defaults(self):
        params = AITranslateSubtitleParams(target_language="en")
        assert params.provider == "gemini"
        assert params.format is None
        assert params.batch_size == 50


class TestAITranslateSubtitleAction:
    def _make_context(self, tmp_path: Path, ai_provider: Any) -> dict[str, Any]:
        return {
            "file": {"name": "test.mp4", "stem": "test", "ext": ".mp4", "path": "/fake"},
            "_work_dir": str(tmp_path),
            "_ai": {"gemini": ai_provider},
        }

    def test_translates_vtt_to_srt(self, tmp_path):
        ctx = self._make_context(tmp_path, FakeTranslateProvider())
        params = AITranslateSubtitleParams(
            provider="gemini", target_language="en", source_language="uk", format="srt"
        )
        action = AITranslateSubtitleAction()
        input_file = str(FIXTURES_DIR / "subtitles" / "sample.vtt")

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=input_file)

        assert result.status == "done"
        assert result.output.endswith(".srt")
        assert Path(result.output).exists()
        assert result.extras["target_language"] == "en"
        assert result.extras["line_count"] == 3

        # Verify translated content
        translated = pysubs2.load(result.output)
        assert translated[0].text == "Hello, world"
        assert translated[1].text == "These are test subtitles"

    def test_preserves_timing(self, tmp_path):
        ctx = self._make_context(tmp_path, FakeTranslateProvider())
        params = AITranslateSubtitleParams(provider="gemini", target_language="en")
        action = AITranslateSubtitleAction()
        input_file = str(FIXTURES_DIR / "subtitles" / "sample.vtt")

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=input_file)

        translated = pysubs2.load(result.output)
        assert translated[0].start == 0
        assert translated[0].end == 1000
        assert translated[1].start == 1500

    def test_same_format_when_none(self, tmp_path):
        """When format=None, output format matches input."""
        ctx = self._make_context(tmp_path, FakeTranslateProvider())
        params = AITranslateSubtitleParams(provider="gemini", target_language="en")
        action = AITranslateSubtitleAction()
        input_file = str(FIXTURES_DIR / "subtitles" / "sample.vtt")

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=input_file)
        assert result.output.endswith(".vtt")

    def test_raises_on_line_count_mismatch(self, tmp_path):
        class BadTranslateProvider:
            def generate(self, prompt, media=None):
                return "1: Only one line"

        ctx = self._make_context(tmp_path, BadTranslateProvider())
        params = AITranslateSubtitleParams(provider="gemini", target_language="en")
        action = AITranslateSubtitleAction()
        input_file = str(FIXTURES_DIR / "subtitles" / "sample.vtt")

        with pytest.raises(RuntimeError, match="mismatch"):
            action.run(ctx, params, executor=MagicMock(), resolved_input=input_file)

    def test_raises_on_empty_subtitle_file(self, tmp_path):
        empty_vtt = tmp_path / "empty.vtt"
        empty_vtt.write_text("WEBVTT\n\n")

        ctx = self._make_context(tmp_path, FakeTranslateProvider())
        params = AITranslateSubtitleParams(provider="gemini", target_language="en")
        action = AITranslateSubtitleAction()

        with pytest.raises(RuntimeError, match="No subtitle events"):
            action.run(ctx, params, executor=MagicMock(), resolved_input=str(empty_vtt))

    def test_multi_batch_translation(self, tmp_path):
        """Verify batching works when batch_size < total lines."""
        call_count = 0

        class CountingProvider:
            def generate(self, prompt, media=None):
                nonlocal call_count
                call_count += 1
                # Parse which lines were requested and return translations
                lines = []
                for line in prompt.strip().splitlines():
                    import re as _re
                    m = _re.match(r"^(\d+):", line.strip())
                    if m:
                        lines.append(f"{m.group(1)}: Translated line {m.group(1)}")
                return "\n".join(lines)

        ctx = self._make_context(tmp_path, CountingProvider())
        params = AITranslateSubtitleParams(
            provider="gemini", target_language="en", batch_size=2
        )
        action = AITranslateSubtitleAction()
        input_file = str(FIXTURES_DIR / "subtitles" / "sample.vtt")

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=input_file)

        assert result.status == "done"
        assert result.extras["line_count"] == 3
        assert call_count == 2  # 3 lines with batch_size=2 = 2 batches

    def test_preserves_ass_style_tags(self, tmp_path):
        """ASS/SSA style override tags should survive translation."""
        class StyleProvider:
            def generate(self, prompt, media=None):
                return "1: Translated bold text"

        # Create an ASS file with style tags
        subs = pysubs2.SSAFile()
        subs.append(pysubs2.SSAEvent(start=0, end=1000, text=r"{\b1}Bold text{\b0}"))
        ass_file = tmp_path / "styled.ass"
        subs.save(str(ass_file))

        ctx = self._make_context(tmp_path, StyleProvider())
        params = AITranslateSubtitleParams(provider="gemini", target_language="en")
        action = AITranslateSubtitleAction()

        result = action.run(ctx, params, executor=MagicMock(), resolved_input=str(ass_file))

        translated = pysubs2.load(result.output)
        # Style tags should be present in the translated output
        assert r"{\b1}" in translated[0].text
        assert r"{\b0}" in translated[0].text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/test_actions_ai.py::TestAITranslateSubtitleAction -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Implement ai.translate_subtitle action**

Create `src/mediariver/actions/ai/translate_subtitle.py`:

```python
"""AI subtitle translation action — translate subtitle files between languages."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import pysubs2
import structlog
from pydantic import BaseModel, Field

from mediariver.actions.ai import SUBTITLE_FORMATS
from mediariver.actions.base import ActionResult, BaseAction
from mediariver.actions.executor import CommandExecutor
from mediariver.actions.registry import register_action

log = structlog.get_logger()

TRANSLATION_PROMPT = """\
Translate the following numbered subtitle lines from {source} to {target}.

Return ONLY the translated lines in the exact same numbered format.
Preserve the line numbers exactly. Do not merge or split lines.
Do not add explanations or commentary.

{lines}
"""


class AITranslateSubtitleParams(BaseModel):
    provider: str = "gemini"
    target_language: str
    source_language: str | None = None
    format: SUBTITLE_FORMATS | None = None
    batch_size: int = Field(default=50, ge=10, le=200)


@register_action("ai.translate_subtitle")
class AITranslateSubtitleAction(BaseAction):
    name = "ai.translate_subtitle"
    params_model = AITranslateSubtitleParams

    def run(
        self,
        context: dict[str, Any],
        params: AITranslateSubtitleParams,
        executor: CommandExecutor,
        resolved_input: str | None = None,
    ) -> ActionResult:
        input_path = resolved_input or context["file"]["path"]
        work_dir = context.get("_work_dir", "/tmp")
        stem = context["file"]["stem"]

        provider = context["_ai"][params.provider]

        # Load subtitles
        subs = pysubs2.load(input_path)
        events = [e for e in subs.events if e.text.strip()]

        if not events:
            raise RuntimeError("No subtitle events found in input file")

        # Extract style tags before translation
        style_maps: list[list[tuple[int, str]]] = []
        for event in events:
            tags = [(m.start(), m.group()) for m in re.finditer(r"\{[^}]*\}", event.text)]
            style_maps.append(tags)

        # Translate in batches
        translated_texts: list[str] = []
        for batch_start in range(0, len(events), params.batch_size):
            batch = events[batch_start : batch_start + params.batch_size]
            batch_translations = self._translate_batch(
                provider, batch, batch_start, params
            )
            translated_texts.extend(batch_translations)

        # Apply translations with style tags re-inserted
        for event, translated, original_tags in zip(events, translated_texts, style_maps):
            event.text = self._reinsert_style_tags(translated, original_tags)

        # Determine output format
        input_ext = Path(input_path).suffix.lstrip(".")
        out_format = params.format or input_ext
        output_path = os.path.join(work_dir, f"{stem}_translated.{out_format}")
        subs.save(output_path, format_=out_format)

        return ActionResult(
            status="done",
            output=output_path,
            extras={
                "source_language": params.source_language or "auto",
                "target_language": params.target_language,
                "format": out_format,
                "line_count": len(events),
            },
        )

    def _translate_batch(
        self,
        provider: Any,
        batch: list[pysubs2.SSAEvent],
        offset: int,
        params: AITranslateSubtitleParams,
    ) -> list[str]:
        """Translate a batch of subtitle events, return list of translated texts."""
        # Build numbered lines
        numbered_lines = []
        for i, event in enumerate(batch):
            # Strip ASS/SSA style tags for translation, we'll keep original styling
            plain_text = re.sub(r"\{[^}]*\}", "", event.text)
            numbered_lines.append(f"{offset + i + 1}: {plain_text}")

        source = params.source_language or "auto-detected language"
        prompt = TRANSLATION_PROMPT.format(
            source=source,
            target=params.target_language,
            lines="\n".join(numbered_lines),
        )

        response = provider.generate(prompt)

        # Parse numbered response
        translations = self._parse_numbered_response(response, len(batch), offset)
        return translations

    def _parse_numbered_response(
        self, response: str, expected_count: int, offset: int
    ) -> list[str]:
        """Parse 'N: text' response format into a list of texts."""
        lines = {}
        for line in response.strip().splitlines():
            match = re.match(r"^(\d+):\s*(.*)$", line.strip())
            if match:
                num = int(match.group(1))
                text = match.group(2).strip()
                lines[num] = text

        result = []
        for i in range(expected_count):
            key = offset + i + 1
            if key not in lines:
                raise RuntimeError(
                    f"Translation line count mismatch: expected line {key} but not found in response"
                )
            result.append(lines[key])

        return result

    @staticmethod
    def _reinsert_style_tags(
        translated: str, original_tags: list[tuple[int, str]]
    ) -> str:
        """Re-insert ASS/SSA style tags into translated text.

        Uses proportional positioning: if a tag was at 30% of the original
        text, it goes at 30% of the translated text.
        """
        if not original_tags:
            return translated

        # Calculate original plain text length (without tags)
        total_tag_len = sum(len(tag) for _, tag in original_tags)
        # Original text with tags removed would have had positions shifted
        # We use the tag's position relative to the full original string length
        # as a proportion to place in the translated string
        result = translated
        offset = 0
        for orig_pos, tag in original_tags:
            if orig_pos == 0:
                # Tags at the start stay at the start
                insert_pos = 0
            else:
                # Proportional positioning
                ratio = orig_pos / max(orig_pos + total_tag_len, 1)
                insert_pos = min(int(ratio * len(translated)), len(translated))
            result = result[: insert_pos + offset] + tag + result[insert_pos + offset :]
            offset += len(tag)

        return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_actions_ai.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mediariver/actions/ai/translate_subtitle.py tests/fixtures/subtitles/ tests/unit/test_actions_ai.py
git commit -m "feat: add ai.translate_subtitle action with pysubs2 format support"
```

---

### Task 10: Register AI actions + smoke test

**Files:**
- Modify: `src/mediariver/actions/__init__.py`

- [ ] **Step 1: Add AI action imports**

In `src/mediariver/actions/__init__.py`, add after the Video actions block:

```python
# isort: split
# AI actions
import mediariver.actions.ai.subtitle  # noqa: F401
import mediariver.actions.ai.translate_subtitle  # noqa: F401
```

- [ ] **Step 2: Write registration test**

Add to `tests/unit/test_actions_ai.py`:

```python
class TestAIActionRegistration:
    def test_subtitle_registered(self):
        from mediariver.actions.registry import ActionRegistry
        assert "ai.subtitle" in ActionRegistry.list_actions()

    def test_translate_subtitle_registered(self):
        from mediariver.actions.registry import ActionRegistry
        assert "ai.translate_subtitle" in ActionRegistry.list_actions()
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/unit/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/mediariver/actions/__init__.py tests/unit/test_actions_ai.py
git commit -m "feat: register ai.subtitle and ai.translate_subtitle actions"
```

---

### Task 11: Integration test with real Gemini API

**Files:**
- Test: `tests/integration/test_ai_gemini.py`

This task requires `GEMINI_API_KEY` in the environment.

- [ ] **Step 1: Create integration test**

Create `tests/integration/test_ai_gemini.py`:

```python
"""Integration tests for Gemini AI provider — requires GEMINI_API_KEY."""

import os
import json
from pathlib import Path

import pytest

from mediariver.ai.gemini import GeminiProvider
from mediariver.config.schema import AIProviderConfig

pytestmark = pytest.mark.integration


@pytest.fixture
def gemini_provider():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set")
    config = AIProviderConfig(provider="gemini", api_key=api_key, model="gemini-3-pro")
    return GeminiProvider("test", config)


class TestGeminiIntegration:
    def test_text_generation(self, gemini_provider):
        result = gemini_provider.generate("Reply with exactly: PONG")
        assert "PONG" in result

    def test_subtitle_generation_with_audio(self, gemini_provider, tmp_path):
        """Test with a tiny generated audio file if available."""
        # This test validates the full flow with a real API call
        # Skip if no test media available
        test_media = Path(__file__).parent.parent / "fixtures" / "media"
        audio_files = list(test_media.glob("*.mp3")) + list(test_media.glob("*.wav"))
        if not audio_files:
            pytest.skip("No test audio files in fixtures/media/")

        result = gemini_provider.generate(
            "Transcribe this audio. Return JSON with language and subtitles array.",
            media=[audio_files[0]],
        )
        data = json.loads(result)
        assert "language" in data
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_ai_gemini.py -v -m integration`
Expected: PASS (or skip if no API key / no media fixtures)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_ai_gemini.py
git commit -m "test: add Gemini API integration tests"
```
