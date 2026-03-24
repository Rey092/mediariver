"""Tests for desktop app configuration."""

import json

import pytest

from desktop.config import AppConfig, load_config, save_config


class TestAppConfig:
    def test_default_config(self):
        config = AppConfig()
        assert config.workflows_dir == "./workflows"
        assert config.log_level == "info"
        assert config.port == 9876
        assert config.env == {}

    def test_config_from_args(self):
        config = AppConfig(
            workflows_dir="C:\\my\\workflows",
            log_level="debug",
            port=8080,
            env={"S3_BUCKET": "test"},
        )
        assert config.workflows_dir == "C:\\my\\workflows"
        assert config.env["S3_BUCKET"] == "test"


class TestLoadSaveConfig:
    def test_load_missing_file_returns_defaults(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.json")
        assert config.port == 9876

    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "config.json"
        config = AppConfig(workflows_dir="/test", env={"KEY": "val"})
        save_config(config, path)

        loaded = load_config(path)
        assert loaded.workflows_dir == "/test"
        assert loaded.env["KEY"] == "val"

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "sub" / "dir" / "config.json"
        save_config(AppConfig(), path)
        assert path.exists()

    def test_load_corrupt_file_returns_defaults(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        config = load_config(path)
        assert config.port == 9876
