"""Tests for command executor (local/docker switching)."""

from unittest.mock import MagicMock, patch
import subprocess

import pytest

from mediariver.actions.executor import CommandExecutor, CommandResult


class TestCommandExecutor:
    def test_local_execution_when_binary_found(self):
        executor = CommandExecutor()
        with patch("shutil.which", return_value="/usr/bin/echo"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["echo", "hello"], returncode=0, stdout="hello\n", stderr=""
            )
            result = executor.run(
                binary="echo",
                args=["hello"],
                docker_image="unused",
                strategy="auto",
            )
            assert result.returncode == 0
            assert result.stdout == "hello\n"
            mock_run.assert_called_once()

    def test_docker_fallback_when_binary_missing(self):
        executor = CommandExecutor()
        mock_manager = MagicMock()
        mock_manager.run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr=""
        )
        executor.docker_manager = mock_manager

        with patch("shutil.which", return_value=None):
            result = executor.run(
                binary="ffmpeg",
                args=["-i", "input.mp4"],
                docker_image="mediariver/ffmpeg:latest",
                strategy="auto",
            )
            mock_manager.run.assert_called_once()
            assert result.returncode == 0

    def test_force_local_fails_if_missing(self):
        executor = CommandExecutor()
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="ffmpeg"):
                executor.run(
                    binary="ffmpeg",
                    args=[],
                    docker_image="unused",
                    strategy="local",
                )

    def test_force_docker(self):
        executor = CommandExecutor()
        mock_manager = MagicMock()
        mock_manager.run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        executor.docker_manager = mock_manager

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = executor.run(
                binary="ffmpeg",
                args=["-version"],
                docker_image="mediariver/ffmpeg:latest",
                strategy="docker",
            )
            mock_manager.run.assert_called_once()
