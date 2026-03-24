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
    def test_basic_transcode_cpu(self, mock_executor, base_context):
        action = VideoTranscodeAction()
        params = action.params_model(preset="h264-web", crf=18, hw="cpu")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.extras["codec"] == "libx264"
        assert result.extras["gpu"] is False

    def test_nvenc_preset(self, mock_executor, base_context):
        action = VideoTranscodeAction()
        params = action.params_model(preset="nvenc-h264", crf=20)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.extras["codec"] == "h264_nvenc"
        assert result.extras["gpu"] is True

    def test_auto_hw_detection(self, mock_executor, base_context):
        # Mock ffmpeg -encoders to return nvenc support
        mock_executor.run.side_effect = [
            CommandResult(returncode=0, stdout="h264_nvenc", stderr=""),  # encoder check
            CommandResult(returncode=0, stdout="", stderr=""),  # actual transcode
        ]
        action = VideoTranscodeAction()
        params = action.params_model(preset="h264-web", crf=18, hw="auto")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.extras["codec"] == "h264_nvenc"
        assert result.extras["gpu"] is True


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


class TestVideoUpscaleAction:
    def test_dandere2x_upscale(self, mock_executor, base_context):
        from mediariver.actions.video.upscale import VideoUpscaleAction

        action = VideoUpscaleAction()
        params = action.params_model(engine="dandere2x", scale=2, gpu=True)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()

    def test_lanczos_upscale(self, mock_executor, base_context):
        from mediariver.actions.video.upscale import VideoUpscaleAction

        action = VideoUpscaleAction()
        params = action.params_model(engine="lanczos", scale=2)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"


class TestVideoPreviewAction:
    def test_creates_gif_preview(self, mock_executor, base_context):
        from mediariver.actions.video.preview import VideoPreviewAction

        action = VideoPreviewAction()
        params = action.params_model(format="gif", duration="3s", fps=10, width=480)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        assert result.output.endswith(".gif")

    def test_creates_webp_preview(self, mock_executor, base_context):
        from mediariver.actions.video.preview import VideoPreviewAction

        action = VideoPreviewAction()
        params = action.params_model(format="webp", duration="5s")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.output.endswith(".webp")


class TestVideoExtractAudioAction:
    def test_extract_audio_copy(self, mock_executor, base_context):
        from mediariver.actions.video.extract_audio import VideoExtractAudioAction

        action = VideoExtractAudioAction()
        params = action.params_model(stream=0, codec="copy")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.status == "done"
        mock_executor.run.assert_called_once()

    def test_extract_audio_aac(self, mock_executor, base_context):
        from mediariver.actions.video.extract_audio import VideoExtractAudioAction

        action = VideoExtractAudioAction()
        params = action.params_model(codec="aac")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mp4")

        assert result.output.endswith(".m4a")


class TestVideoExtractSubsAction:
    def test_extract_srt(self, mock_executor, base_context):
        from mediariver.actions.video.extract_subs import VideoExtractSubsAction

        action = VideoExtractSubsAction()
        params = action.params_model(format="srt", stream=0)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/video.mkv")

        assert result.status == "done"
        assert result.output.endswith(".srt")
        mock_executor.run.assert_called_once()


class TestVideoConcatAction:
    def test_demuxer_concat(self, mock_executor, base_context):
        from mediariver.actions.video.concat import VideoConcatAction

        action = VideoConcatAction()
        params = action.params_model(mode="demuxer", inputs=["/tmp/part1.mp4", "/tmp/part2.mp4"])
        result = action.run(base_context, params, mock_executor, resolved_input=None)

        assert result.status == "done"
        mock_executor.run.assert_called_once()
