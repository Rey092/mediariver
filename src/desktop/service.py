"""Engine subprocess management — start, stop, restart, log capture."""

from __future__ import annotations

import collections
import os
import signal
import subprocess
import sys
import threading
import time

from desktop.config import AppConfig

_MAX_LOG_LINES = 10_000


class EngineService:
    """Manages the mediariver engine as a subprocess."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._process: subprocess.Popen | None = None
        self._logs: collections.deque[str] = collections.deque(maxlen=_MAX_LOG_LINES)
        self._log_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._started_at: float | None = None

    def start(self) -> None:
        if self.is_running():
            return
        cmd = self._build_command()
        env = self._build_env()
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        self._started_at = time.time()
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if not self._process or not self.is_running():
            return
        try:
            if sys.platform == "win32":
                os.kill(self._process.pid, signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()
        except (OSError, ProcessLookupError):
            pass
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=2)
        self._process = None
        self._started_at = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    def get_uptime(self) -> float:
        if self._started_at and self.is_running():
            return time.time() - self._started_at
        return 0.0

    def get_logs(self, last_n: int | None = None) -> list[str]:
        with self._log_lock:
            if last_n:
                return list(self._logs)[-last_n:]
            return list(self._logs)

    def _build_command(self) -> list[str]:
        cmd = [sys.executable, "-m", "mediariver", "run"]
        cmd.extend(["--workflows-dir", self.config.workflows_dir])
        if self.config.database_url:
            cmd.extend(["--database-url", self.config.database_url])
        cmd.extend(["--log-level", self.config.log_level])
        return cmd

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self.config.env)
        return env

    def _read_output(self) -> None:
        if not self._process or not self._process.stdout:
            return
        for line in self._process.stdout:
            stripped = line.strip()
            if stripped:
                with self._log_lock:
                    self._logs.append(stripped)
