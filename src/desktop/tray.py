"""MediaRiver tray app — main entry point for Windows desktop."""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pystray
import uvicorn
from PIL import Image, ImageDraw

from desktop.config import DEFAULT_CONFIG_PATH, load_config, save_config
from desktop.server import create_app
from desktop.service import EngineService
from desktop.updater import Updater

_LOG_DIR = Path.home() / ".mediariver"
_LOG_FILE = _LOG_DIR / "desktop.log"


def _setup_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _create_icon_image() -> Image.Image:
    """Create a simple tray icon: green circle on dark background."""
    size = 64
    img = Image.new("RGBA", (size, size), (26, 26, 26, 255))
    draw = ImageDraw.Draw(img)
    margin = 12
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(34, 197, 94, 255),  # green
    )
    return img


def main() -> None:
    _setup_logging()
    log = logging.getLogger("mediariver.desktop")

    config = load_config()
    log.info("Config loaded from %s", DEFAULT_CONFIG_PATH)

    if not _port_available(config.port):
        log.error("Port %d already in use", config.port)
        sys.exit(1)

    # Auto-update on start
    repo_dir = Path(__file__).resolve().parent.parent
    updater = Updater(repo_dir)
    try:
        status = updater.check()
        if not status.up_to_date and not status.error:
            log.info("Update available: %d commits behind, applying...", status.commits_behind)
            if updater.apply():
                log.info("Updated, restarting...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        log.warning("Update check failed: %s", e)

    # Start engine
    service = EngineService(config)
    service.start()
    log.info("Engine started")

    # Start web server in thread
    app = create_app(config, service, updater)

    def run_server():
        try:
            uvicorn.run(app, host="127.0.0.1", port=config.port, log_level="warning")
        except Exception as e:
            log.error("Server thread crashed: %s", e, exc_info=True)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    log.info("Web UI at http://127.0.0.1:%d", config.port)

    # Tray callbacks
    def open_ui(icon, item):
        webbrowser.open(f"http://127.0.0.1:{config.port}")

    def restart_engine(icon, item):
        service.restart()
        log.info("Engine restarted via tray")

    def restart_app(icon, item):
        log.info("Full app restart via tray")
        service.stop()
        icon.stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def check_updates(icon, item):
        s = updater.check()
        if s.up_to_date:
            icon.notify("MediaRiver is up to date")
        elif s.error:
            icon.notify(f"Update check failed: {s.error}")
        else:
            icon.notify(f"Update available: {s.commits_behind} commits behind")

    def quit_app(icon, item):
        log.info("Shutting down...")
        service.stop()
        icon.stop()

    icon_image = _create_icon_image()

    icon = pystray.Icon(
        "MediaRiver",
        icon_image,
        "MediaRiver",
        menu=pystray.Menu(
            pystray.MenuItem("Open UI", open_ui, default=True),
            pystray.MenuItem("Restart Engine", restart_engine),
            pystray.MenuItem("Restart App", restart_app),
            pystray.MenuItem("Check for Updates", check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", quit_app),
        ),
    )

    # Watchdog
    def watchdog():
        import time
        nonlocal server_thread
        while True:
            time.sleep(30)
            if not server_thread.is_alive():
                log.error("Server thread died, restarting")
                server_thread = threading.Thread(target=run_server, daemon=True)
                server_thread.start()

    threading.Thread(target=watchdog, daemon=True).start()

    # First-run: show pin notification and open UI
    if config.first_run:
        def _first_run():
            import time
            time.sleep(2)
            icon.notify(
                "MediaRiver is running! Right-click the tray icon for options.\n"
                "Tip: Pin this icon — go to Settings > Taskbar > Other system tray icons > MediaRiver",
                "MediaRiver",
            )
            webbrowser.open(f"http://127.0.0.1:{config.port}")
            config.first_run = False
            save_config(config)

        threading.Thread(target=_first_run, daemon=True).start()

    log.info("Tray icon ready")
    icon.run()


if __name__ == "__main__":
    main()
