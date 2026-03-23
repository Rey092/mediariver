"""Tests for audio actions."""

import json
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
        "file": {"name": "audio.mp3", "stem": "audio", "ext": ".mp3", "path": "/tmp/audio.mp3", "hash": "h", "size": 5000},
        "env": {},
        "steps": {},
        "_work_dir": str(work_dir),
    }


class TestAudioInfoAction:
    def test_parses_ffprobe_json(self, mock_executor, base_context):
        from mediariver.actions.audio.info import AudioInfoAction

        probe_output = json.dumps({
            "streams": [{"codec_type": "audio", "codec_name": "mp3", "bit_rate": "320000", "sample_rate": "44100", "channels": 2}],
            "format": {"duration": "180.5"},
        })
        mock_executor.run.return_value = CommandResult(returncode=0, stdout=probe_output, stderr="")

        action = AudioInfoAction()
        result = action.run(base_context, action.params_model(), mock_executor, resolved_input="/tmp/audio.mp3")

        assert result.status == "done"
        assert result.extras["codec"] == "mp3"
        assert result.extras["sample_rate"] == "44100"
        assert result.extras["channels"] == 2
        assert result.extras["duration"] == 180.5


class TestAudioNormalizeAction:
    def test_two_pass_loudnorm(self, mock_executor, base_context):
        from mediariver.actions.audio.normalize import AudioNormalizeAction

        pass1_stderr = (
            '{"input_i": "-24.5", "input_tp": "-3.2", "input_lra": "8.1",'
            ' "input_thresh": "-35.0", "target_offset": "0.5"}'
        )
        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout="", stderr=pass1_stderr),
            CommandResult(returncode=0, stdout="", stderr=""),
        ]

        action = AudioNormalizeAction()
        params = action.params_model(target_i=-16, target_tp=-1.5, target_lra=11)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/audio.mp3")

        assert result.status == "done"
        assert mock_executor.run.call_count == 2


class TestAudioConvertAction:
    def test_convert_to_aac(self, mock_executor, base_context):
        from mediariver.actions.audio.convert import AudioConvertAction

        action = AudioConvertAction()
        params = action.params_model(codec="aac", bitrate="256k")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/audio.mp3")

        assert result.status == "done"
        mock_executor.run.assert_called_once()

    def test_convert_to_flac(self, mock_executor, base_context):
        from mediariver.actions.audio.convert import AudioConvertAction

        action = AudioConvertAction()
        params = action.params_model(codec="flac")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/audio.mp3")

        assert result.status == "done"
        assert result.output.endswith(".flac")


class TestAudioHlsAction:
    def test_creates_hls_variants(self, mock_executor, base_context):
        from mediariver.actions.audio.hls import AudioHlsAction

        action = AudioHlsAction()
        params = action.params_model(
            variants=[{"bitrate": "128k"}, {"bitrate": "256k"}],
            segment_time=10,
        )
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/audio.mp3")

        assert result.status == "done"
        assert result.extras.get("output_dir") is not None
        # One ffmpeg call per variant
        assert mock_executor.run.call_count == 2


class TestAudioDurationCheckAction:
    def test_passes_within_tolerance(self, mock_executor, base_context):
        from mediariver.actions.audio.duration_check import AudioDurationCheckAction

        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout='{"format":{"duration":"180.0"}}', stderr=""),
            CommandResult(returncode=0, stdout='{"format":{"duration":"180.3"}}', stderr=""),
        ]

        action = AudioDurationCheckAction()
        params = action.params_model(original="/tmp/orig.mp3", processed="/tmp/proc.m4a", tolerance_ms=500)
        result = action.run(base_context, params, mock_executor)

        assert result.status == "done"

    def test_fails_beyond_tolerance(self, mock_executor, base_context):
        from mediariver.actions.audio.duration_check import AudioDurationCheckAction

        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout='{"format":{"duration":"180.0"}}', stderr=""),
            CommandResult(returncode=0, stdout='{"format":{"duration":"175.0"}}', stderr=""),
        ]

        action = AudioDurationCheckAction()
        params = action.params_model(
            original="/tmp/orig.mp3", processed="/tmp/proc.m4a",
            tolerance_ms=500, on_mismatch="fail"
        )
        with pytest.raises(RuntimeError, match="Duration mismatch"):
            action.run(base_context, params, mock_executor)

    def test_warns_beyond_tolerance(self, mock_executor, base_context):
        from mediariver.actions.audio.duration_check import AudioDurationCheckAction

        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout='{"format":{"duration":"180.0"}}', stderr=""),
            CommandResult(returncode=0, stdout='{"format":{"duration":"175.0"}}', stderr=""),
        ]

        action = AudioDurationCheckAction()
        params = action.params_model(
            original="/tmp/orig.mp3", processed="/tmp/proc.m4a",
            tolerance_ms=500, on_mismatch="warn"
        )
        result = action.run(base_context, params, mock_executor)

        assert result.status == "done"
        assert "warning" in result.extras
