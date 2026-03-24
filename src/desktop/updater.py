"""Git-based auto-updater — check for new commits and apply."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateStatus:
    up_to_date: bool
    commits_behind: int = 0
    current: str = ""
    remote: str = ""
    error: str | None = None


class Updater:
    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = str(repo_path)

    def check(self) -> UpdateStatus:
        try:
            self._git("fetch", "origin", "main", "--quiet")
            current = self._git("rev-parse", "--short", "HEAD").strip()
            remote = self._git("rev-parse", "--short", "origin/main").strip()
            behind_str = self._git("rev-list", "HEAD..origin/main", "--count").strip()
            behind = int(behind_str)
            return UpdateStatus(
                up_to_date=behind == 0,
                commits_behind=behind,
                current=current,
                remote=remote,
            )
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            return UpdateStatus(up_to_date=True, error=str(e))

    def apply(self) -> bool:
        try:
            status = self._git("status", "--porcelain").strip()
            if status:
                return False
            self._git("pull", "origin", "main")
            diff = self._git("diff", "HEAD~1", "--name-only")
            if "pyproject.toml" in diff:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-e", ".[desktop]", "--quiet"],
                    cwd=self.repo_path,
                    check=True,
                )
            return True
        except (subprocess.CalledProcessError, OSError):
            return False

    def get_current_version(self) -> str:
        try:
            return self._git("rev-parse", "--short", "HEAD").strip()
        except (subprocess.CalledProcessError, OSError):
            return "unknown"

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
