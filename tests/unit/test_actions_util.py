"""Tests for utility actions."""

from unittest.mock import MagicMock

import pytest

from mediariver.actions.executor import CommandResult


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.run.return_value = CommandResult(returncode=0, stdout="", stderr="")
    return executor


@pytest.fixture
def base_context(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    return {
        "file": {"name": "video.mp4", "stem": "video", "ext": ".mp4", "path": "/tmp/video.mp4", "hash": "h", "size": 1000},
        "env": {},
        "steps": {},
        "_work_dir": str(work_dir),
    }


class TestWatermarkAction:
    def test_image_watermark(self, mock_executor, base_context):
        from mediariver.actions.util.watermark import WatermarkAction

        action = WatermarkAction()
        params = action.params_model(type="image", image="/tmp/logo.png", position="bottom-right", opacity=0.3)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()


class TestStripMetadataAction:
    def test_strip_with_ffmpeg(self, mock_executor, base_context):
        from mediariver.actions.util.strip_metadata import StripMetadataAction

        action = StripMetadataAction()
        params = action.params_model(tool="ffmpeg")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-map_metadata" in args


class TestOcrAction:
    def test_ocr_extraction(self, mock_executor, base_context):
        from mediariver.actions.util.ocr import OcrAction

        action = OcrAction()
        params = action.params_model(lang="eng+jpn", psm=6)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        mock_executor.run.assert_called_once()


class TestHashVerifyAction:
    def test_generate_blake3(self, mock_executor, tmp_path):
        from mediariver.actions.util.hash_verify import HashVerifyAction

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")

        ctx = {
            "file": {"path": str(test_file), "stem": "test", "name": "test.bin", "ext": ".bin", "hash": "h", "size": 11},
            "env": {},
            "steps": {},
            "_work_dir": str(tmp_path),
        }

        action = HashVerifyAction()
        params = action.params_model(algo="blake3", mode="generate")
        result = action.run(ctx, params, mock_executor, resolved_input=str(test_file))

        assert result.status == "done"
        assert "hash" in result.extras
        assert len(result.extras["hash"]) == 64  # hex digest

    def test_verify_sha256_pass(self, mock_executor, tmp_path):
        import hashlib
        from mediariver.actions.util.hash_verify import HashVerifyAction

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()

        ctx = {
            "file": {"path": str(test_file), "stem": "test", "name": "test.bin", "ext": ".bin", "hash": "h", "size": 11},
            "env": {},
            "steps": {},
            "_work_dir": str(tmp_path),
        }

        action = HashVerifyAction()
        params = action.params_model(algo="sha256", mode="verify", expected=expected)
        result = action.run(ctx, params, mock_executor, resolved_input=str(test_file))

        assert result.status == "done"

    def test_verify_sha256_fail(self, mock_executor, tmp_path):
        from mediariver.actions.util.hash_verify import HashVerifyAction

        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")

        ctx = {
            "file": {"path": str(test_file), "stem": "test", "name": "test.bin", "ext": ".bin", "hash": "h", "size": 11},
            "env": {},
            "steps": {},
            "_work_dir": str(tmp_path),
        }

        action = HashVerifyAction()
        params = action.params_model(algo="sha256", mode="verify", expected="wrong_hash")
        with pytest.raises(RuntimeError, match="mismatch"):
            action.run(ctx, params, mock_executor, resolved_input=str(test_file))
