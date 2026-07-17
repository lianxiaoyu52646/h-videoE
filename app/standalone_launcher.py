"""Standalone Windows entry: start local API, worker, and open the app in the default browser."""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    os.chdir(Path(sys.executable).parent)

os.environ.setdefault("APP_MODE", "desktop")
os.environ.setdefault("LOCAL_AUTO_USER", "1")
os.environ.setdefault("INLINE_WORKER", "1")
os.environ.setdefault("DESKTOP_HOT_RELOAD", "0")

import uvicorn  # noqa: E402

from app import database, security  # noqa: E402
from app.config import settings  # noqa: E402
from app.desktop_runtime import ensure_worker_started  # noqa: E402
from app.main import app  # noqa: E402

logger = logging.getLogger("videoenglish.standalone")


def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _open_browser_when_ready() -> None:
    host = settings.desktop_host
    port = settings.desktop_port
    url = settings.desktop_base_url
    if _wait_for_port(host, port):
        webbrowser.open(url)
        logger.info("opened browser at %s", url)
    else:
        logger.error("backend did not become ready on %s:%s", host, port)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings.ensure_runtime_dirs()
    database.init_db()
    if settings.local_auto_user:
        security.ensure_default_user_exists()
    ensure_worker_started()
    threading.Thread(target=_open_browser_when_ready, name="browser-launcher", daemon=True).start()
    uvicorn.run(app, host=settings.desktop_host, port=settings.desktop_port, access_log=False)


if __name__ == "__main__":
    main()
