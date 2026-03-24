"""Tests for FastAPI web server."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from desktop.config import AppConfig
from desktop.updater import UpdateStatus


@pytest.fixture
def app():
    from desktop.server import create_app

    config = AppConfig()
    service = MagicMock()
    service.is_running.return_value = True
    service.get_uptime.return_value = 3600.0
    service.get_logs.return_value = ["2024-01-01 [info] test log line"]
    updater = MagicMock()
    updater.check.return_value = UpdateStatus(up_to_date=True, current="abc1234", remote="abc1234")
    updater.get_current_version.return_value = "abc1234"
    return create_app(config, service, updater)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestPages:
    def test_dashboard(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "MediaRiver" in response.text

    def test_files_page(self, client):
        response = client.get("/files")
        assert response.status_code == 200

    def test_workflows_page(self, client):
        response = client.get("/workflows")
        assert response.status_code == 200

    def test_logs_page(self, client):
        response = client.get("/logs")
        assert response.status_code == 200

    def test_settings_page(self, client):
        response = client.get("/settings")
        assert response.status_code == 200


class TestAPI:
    def test_api_status(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert data["uptime"] == 3600.0

    def test_api_engine_restart(self, client):
        response = client.post("/api/engine/restart")
        assert response.status_code == 200

    def test_api_update_check(self, client):
        response = client.get("/api/update/check")
        assert response.status_code == 200
        data = response.json()
        assert data["up_to_date"] is True
