"""Tests for git-based updater."""

from unittest.mock import patch
import subprocess

import pytest

from desktop.updater import Updater, UpdateStatus


class TestUpdater:
    def test_check_up_to_date(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git fetch
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),  # local hash
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),  # remote hash
                subprocess.CompletedProcess([], 0, stdout="0\n"),  # rev-list count
            ]
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is True
            assert status.commits_behind == 0

    def test_check_behind(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess([], 0),  # git fetch
                subprocess.CompletedProcess([], 0, stdout="abc1234\n"),
                subprocess.CompletedProcess([], 0, stdout="def5678\n"),
                subprocess.CompletedProcess([], 0, stdout="3\n"),
            ]
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is False
            assert status.commits_behind == 3
            assert status.current == "abc1234"
            assert status.remote == "def5678"

    def test_check_fetch_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            updater = Updater("/fake/repo")
            status = updater.check()
            assert status.up_to_date is True
            assert status.error is not None

    def test_get_current_version(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="abc1234\n")
            updater = Updater("/fake/repo")
            assert updater.get_current_version() == "abc1234"
