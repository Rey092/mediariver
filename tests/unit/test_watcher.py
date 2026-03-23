"""Tests for directory watcher and file filtering."""

import pytest

from mediariver.watcher.filter import matches_extensions
from mediariver.watcher.poller import parse_interval


class TestMatchesExtensions:
    def test_matching_extension(self):
        assert matches_extensions("video.mp4", [".mp4", ".mkv"]) is True

    def test_non_matching_extension(self):
        assert matches_extensions("readme.txt", [".mp4", ".mkv"]) is False

    def test_case_insensitive(self):
        assert matches_extensions("video.MP4", [".mp4"]) is True

    def test_no_extension(self):
        assert matches_extensions("Makefile", [".mp4"]) is False

    def test_empty_extensions(self):
        assert matches_extensions("video.mp4", []) is False


class TestParseInterval:
    def test_seconds(self):
        assert parse_interval("30s") == 30.0

    def test_minutes(self):
        assert parse_interval("5m") == 300.0

    def test_hours(self):
        assert parse_interval("1h") == 3600.0

    def test_bare_number_defaults_to_seconds(self):
        assert parse_interval("10") == 10.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_interval("abc")
