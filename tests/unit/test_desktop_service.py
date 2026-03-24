"""Tests for engine service subprocess management."""

import pytest

from desktop.config import AppConfig
from desktop.service import EngineService


class TestEngineService:
    def test_build_command(self):
        config = AppConfig(workflows_dir="/wf", database_url="sqlite:///test.db", log_level="debug")
        svc = EngineService(config)
        cmd = svc._build_command()
        assert "--workflows-dir" in cmd
        assert "/wf" in cmd
        assert "--log-level" in cmd
        assert "debug" in cmd
        assert "--database-url" in cmd

    def test_build_command_no_db_url(self):
        config = AppConfig(workflows_dir="/wf")
        svc = EngineService(config)
        cmd = svc._build_command()
        assert "--database-url" not in cmd

    def test_build_env(self):
        config = AppConfig(env={"S3_BUCKET": "test", "API_KEY": "secret"})
        svc = EngineService(config)
        env = svc._build_env()
        assert env["S3_BUCKET"] == "test"
        assert env["API_KEY"] == "secret"

    def test_not_running_initially(self):
        svc = EngineService(AppConfig())
        assert svc.is_running() is False

    def test_get_logs_empty(self):
        svc = EngineService(AppConfig())
        assert svc.get_logs() == []

    def test_get_uptime_zero_when_stopped(self):
        svc = EngineService(AppConfig())
        assert svc.get_uptime() == 0.0
