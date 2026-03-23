"""Tests for image actions."""

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
        "file": {"name": "page.jpg", "stem": "page", "ext": ".jpg", "path": "/tmp/page.jpg", "hash": "h", "size": 50000},
        "env": {},
        "steps": {},
        "_work_dir": str(work_dir),
    }


class TestImageInfoAction:
    def test_parses_identify_output(self, mock_executor, base_context):
        from mediariver.actions.image.info import ImageInfoAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="1200 1800 JPEG sRGB 2160000", stderr="")

        action = ImageInfoAction()
        result = action.run(base_context, action.params_model(), mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        assert result.extras["width"] == 1200
        assert result.extras["height"] == 1800
        assert result.extras["format"] == "JPEG"
        assert result.extras["pixel_count"] == 2160000
        assert result.extras["orientation"] == "portrait"

    def test_landscape_orientation(self, mock_executor, base_context):
        from mediariver.actions.image.info import ImageInfoAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="1920 1080 PNG sRGB 2073600", stderr="")

        action = ImageInfoAction()
        result = action.run(base_context, action.params_model(), mock_executor, resolved_input="/tmp/page.jpg")

        assert result.extras["orientation"] == "landscape"


class TestImageConvertAction:
    def test_convert_to_webp(self, mock_executor, base_context):
        from mediariver.actions.image.convert import ImageConvertAction

        action = ImageConvertAction()
        params = action.params_model(format="webp", quality=85)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        assert result.output.endswith(".webp")
        mock_executor.run.assert_called_once()

    def test_convert_to_avif(self, mock_executor, base_context):
        from mediariver.actions.image.convert import ImageConvertAction

        action = ImageConvertAction()
        params = action.params_model(format="avif", quality=70)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.output.endswith(".avif")


class TestImageResizeAction:
    def test_resize_contain(self, mock_executor, base_context):
        from mediariver.actions.image.resize import ImageResizeAction

        action = ImageResizeAction()
        params = action.params_model(width=400, fit="contain")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        mock_executor.run.assert_called_once()

    def test_resize_cover(self, mock_executor, base_context):
        from mediariver.actions.image.resize import ImageResizeAction

        action = ImageResizeAction()
        params = action.params_model(width=400, height=400, fit="cover")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"


class TestImageCropAction:
    def test_auto_crop(self, mock_executor, base_context):
        from mediariver.actions.image.crop import ImageCropAction

        action = ImageCropAction()
        params = action.params_model(mode="auto", auto_color="detect")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-trim" in args

    def test_manual_crop(self, mock_executor, base_context):
        from mediariver.actions.image.crop import ImageCropAction

        action = ImageCropAction()
        params = action.params_model(mode="manual", rect={"x": 10, "y": 20, "w": 500, "h": 700})
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-crop" in args


class TestImageOptimizeAction:
    def test_optimize_webp(self, mock_executor, base_context):
        from mediariver.actions.image.optimize import ImageOptimizeAction

        action = ImageOptimizeAction()
        params = action.params_model(engine="cwebp", quality=85)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        mock_executor.run.assert_called_once()


class TestImageUpscaleAction:
    def test_realesrgan_upscale(self, mock_executor, base_context):
        from mediariver.actions.image.upscale import ImageUpscaleAction

        action = ImageUpscaleAction()
        params = action.params_model(engine="realesrgan", scale=2)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        mock_executor.run.assert_called_once()
        call_kwargs = mock_executor.run.call_args.kwargs
        assert call_kwargs.get("strategy") == "docker"


class TestImageOrientationCheckAction:
    def test_matches_portrait(self, mock_executor, base_context):
        from mediariver.actions.image.orientation_check import ImageOrientationCheckAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="800 1200", stderr="")

        action = ImageOrientationCheckAction()
        params = action.params_model(expect="portrait")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"

    def test_fails_on_mismatch(self, mock_executor, base_context):
        from mediariver.actions.image.orientation_check import ImageOrientationCheckAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="1920 1080", stderr="")

        action = ImageOrientationCheckAction()
        params = action.params_model(expect="portrait")
        with pytest.raises(RuntimeError, match="orientation"):
            action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")


class TestImagePixelCheckAction:
    def test_passes_within_bounds(self, mock_executor, base_context):
        from mediariver.actions.image.pixel_check import ImagePixelCheckAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="2073600", stderr="")

        action = ImagePixelCheckAction()
        params = action.params_model(min_pixels=10000, max_pixels=50000000)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"

    def test_fails_below_min(self, mock_executor, base_context):
        from mediariver.actions.image.pixel_check import ImagePixelCheckAction

        mock_executor.run.return_value = CommandResult(returncode=0, stdout="500", stderr="")

        action = ImagePixelCheckAction()
        params = action.params_model(min_pixels=10000)
        with pytest.raises(RuntimeError, match="below"):
            action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")


class TestImageFlipRotateAction:
    def test_rotate_90(self, mock_executor, base_context):
        from mediariver.actions.image.flip_rotate import ImageFlipRotateAction

        action = ImageFlipRotateAction()
        params = action.params_model(rotate=90)
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-rotate" in args

    def test_flip_horizontal(self, mock_executor, base_context):
        from mediariver.actions.image.flip_rotate import ImageFlipRotateAction

        action = ImageFlipRotateAction()
        params = action.params_model(flip="horizontal")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-flop" in args

    def test_auto_orient(self, mock_executor, base_context):
        from mediariver.actions.image.flip_rotate import ImageFlipRotateAction

        action = ImageFlipRotateAction()
        params = action.params_model(rotate="exif-auto")
        result = action.run(base_context, params, mock_executor, resolved_input="/tmp/page.jpg")

        assert result.status == "done"
        args = mock_executor.run.call_args.kwargs.get("args", [])
        assert "-auto-orient" in args
