"""Tests for video actions — mock executor, verify ffmpeg args."""

import json
from unittest.mock import MagicMock

import pytest

from mediariver.actions.executor import CommandResult
from mediariver.actions.video.crop import VideoCropAction
from mediariver.actions.video.hls import VideoHlsAction
from mediariver.actions.video.info import VideoInfoAction
from mediariver.actions.video.normalize_audio import VideoNormalizeAudioAction
from mediariver.actions.video.thumbnail import VideoThumbnailAction
from mediariver.actions.video.transcode import VideoTranscodeAction


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
        "file": {
            "name": "video.mp4",
            "stem": "video",
            "ext": ".mp4",
            "path": "/tmp/video.mp4",
            "hash": "h",
            "size": 1000,
        },
        "env": {},
        "steps": {},
        "_work_dir": str(work_dir),
    }


class TestVideoInfoAction:
    def test_parses_ffprobe_json(self, mock_executor, base_context):
        probe_output = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "r_frame_rate": "24/1",
                        "duration": "120.5",
                        "bit_rate": "5000000",
                    }
                ],
                "format": {"duration": "120.5"},
            }
        )
        mock_executor.run.return_value = CommandResult(returncode=0, stdout=probe_output, stderr="")

        action = VideoInfoAction()
        params = action.params_model()
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.extras["width"] == 1920
        assert result.extras["height"] == 1080
        assert result.extras["codec"] == "h264"

    def test_uses_resolved_input(self, mock_executor, base_context):
        probe_output = json.dumps(
            {
                "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}],
                "format": {"duration": "10"},
            }
        )
        mock_executor.run.return_value = CommandResult(returncode=0, stdout=probe_output, stderr="")

        action = VideoInfoAction()
        params = action.params_model()
        action.run(base_context, params, mock_executor, resolved_input="/other/path.mp4")

        call_args = mock_executor.run.call_args
        assert "/other/path.mp4" in call_args.kwargs.get("args", call_args[1].get("args", []))


class TestVideoCropAction:
    def test_builds_crop_command(self, mock_executor, base_context):
        action = VideoCropAction()
        params = action.params_model(mode="ratio", ratio="16:9", codec="libx264", crf=16)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()


class TestVideoTranscodeAction:
    def test_basic_transcode(self, mock_executor, base_context):
        action = VideoTranscodeAction()
        params = action.params_model(preset="h264-web", crf=18)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()


class TestVideoHlsAction:
    def test_creates_hls_variants(self, mock_executor, base_context):
        action = VideoHlsAction()
        params = action.params_model(
            variants=[
                {"height": 360, "video_bitrate": "600k", "audio_bitrate": "96k"},
                {"height": 720, "video_bitrate": "2500k", "audio_bitrate": "192k"},
            ],
            segment_time=6,
        )
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.extras.get("output_dir") is not None


class TestVideoNormalizeAudioAction:
    def test_two_pass_loudnorm(self, mock_executor, base_context):
        pass1_stderr = (
            '{"input_i": "-24.5", "input_tp": "-3.2", "input_lra": "8.1",'
            ' "input_thresh": "-35.0", "target_offset": "0.5"}'
        )
        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout="", stderr=pass1_stderr),
            CommandResult(returncode=0, stdout="", stderr=""),
        ]

        action = VideoNormalizeAudioAction()
        params = action.params_model(target_i=-16, target_tp=-1.5, target_lra=11)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert mock_executor.run.call_count == 2


class TestVideoThumbnailAction:
    def test_single_thumbnail(self, mock_executor, base_context):
        action = VideoThumbnailAction()
        params = action.params_model(mode="single", at="50%", width=320)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()
