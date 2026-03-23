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
