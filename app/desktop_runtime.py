from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn

def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


os.environ.setdefault("APP_MODE", "desktop")
os.environ.setdefault("LOCAL_AUTO_USER", "1")
os.environ.setdefault("DESKTOP_HOT_RELOAD", "1")
if _env_bool("DESKTOP_HOT_RELOAD", True):
    os.environ.setdefault("INLINE_WORKER", "1")
else:
    os.environ.setdefault("INLINE_WORKER", "0")

from app import database, security  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.worker import run_forever  # noqa: E402

logger = logging.getLogger("videoenglish.desktop")
_worker_thread: threading.Thread | None = None


def _worker_main() -> None:
    asyncio.run(run_forever(poll_seconds=1.0))


def ensure_worker_started() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(
        target=_worker_main,
        name="videoenglish-worker",
        daemon=True,
    )
    _worker_thread.start()
    logger.info("desktop worker started")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings.ensure_runtime_dirs()
    database.init_db()
    if settings.local_auto_user:
        security.ensure_default_user_exists()
    if not settings.desktop_hot_reload:
        ensure_worker_started()
    uvicorn.run(
        "app.main:app" if settings.desktop_hot_reload else app,
        host=settings.desktop_host,
        port=settings.desktop_port,
        reload=settings.desktop_hot_reload,
        reload_dirs=[str(Path(__file__).resolve().parent)] if settings.desktop_hot_reload else None,
        reload_includes=["*.py", "*.html", "*.js", "*.css"] if settings.desktop_hot_reload else None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
