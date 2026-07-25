from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _app_package_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "app"
    return Path(__file__).resolve().parent


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return default


def _default_app_mode() -> str:
    mode = (os.getenv("APP_MODE") or "desktop").strip().lower()
    return mode or "desktop"


def _default_home_dir() -> Path:
    explicit = (os.getenv("VIDEOENGLISH_HOME") or "").strip()
    if explicit:
        return Path(explicit).expanduser()

    if os.name == "nt":
        base = (
            os.getenv("LOCALAPPDATA")
            or os.getenv("APPDATA")
            or str(Path.home() / "AppData" / "Local")
        )
        return Path(base) / "VideoEnglish"

    xdg = (os.getenv("XDG_DATA_HOME") or "").strip()
    if xdg:
        return Path(xdg) / "VideoEnglish"
    return Path.home() / ".videoenglish"


def _default_database_url() -> str:
    configured = (os.getenv("DATABASE_URL") or "").strip()
    if configured:
        # Render / Heroku style postgres:// → SQLAlchemy + psycopg
        if configured.startswith("postgres://"):
            configured = "postgresql+psycopg://" + configured[len("postgres://") :]
        elif configured.startswith("postgresql://") and "+psycopg" not in configured:
            configured = "postgresql+psycopg://" + configured[len("postgresql://") :]
        return configured
    if _default_app_mode() == "desktop":
        db_path = _default_home_dir() / "data" / "videoenglish.sqlite3"
        return f"sqlite:///{db_path.as_posix()}"
    return "sqlite:///./db.sqlite3"


@dataclass(slots=True)
class Settings:
    app_name: str = field(
        default_factory=lambda: os.getenv("APP_NAME", "WordPop 单词泡泡")
    )
    app_mode: str = field(default_factory=_default_app_mode)
    database_url: str = field(default_factory=_default_database_url)
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me"))
    local_auto_user: bool = field(
        default_factory=lambda: _parse_bool(
            os.getenv("LOCAL_AUTO_USER"),
            _default_app_mode() == "desktop",
        )
    )
    auto_install_wordbooks: bool = field(
        default_factory=lambda: _parse_bool(os.getenv("AUTO_INSTALL_WORDBOOKS"), True)
    )
    inline_worker: bool = field(default_factory=lambda: _parse_bool(os.getenv("INLINE_WORKER"), True))
    default_user_email: str = field(default_factory=lambda: os.getenv("DEFAULT_USER_EMAIL", "local@videoenglish.local"))
    default_user_name: str = field(default_factory=lambda: os.getenv("DEFAULT_USER_NAME", "Local User"))
    cors_origins: list[str] = field(default_factory=lambda: _parse_csv(os.getenv("CORS_ORIGINS")))
    auth_cookie_name: str = "ve_session"
    api_token_prefix: str = "ve_"
    session_days: int = 30
    desktop_host: str = field(default_factory=lambda: os.getenv("DESKTOP_HOST", "127.0.0.1"))
    desktop_port: int = field(default_factory=lambda: _parse_int(os.getenv("DESKTOP_PORT"), 18555))
    desktop_hot_reload: bool = field(default_factory=lambda: _parse_bool(os.getenv("DESKTOP_HOT_RELOAD"), False))
    desktop_profile_name: str = field(default_factory=lambda: os.getenv("DESKTOP_PROFILE", "default"))
    app_home_dir: Path = field(default_factory=_default_home_dir)
    app_data_dir: Path = field(default_factory=lambda: _default_home_dir() / "data")
    app_cache_dir: Path = field(default_factory=lambda: _default_home_dir() / "cache")
    app_book_cache_dir: Path = field(default_factory=lambda: _default_home_dir() / "cache" / "books")
    app_log_dir: Path = field(default_factory=lambda: _default_home_dir() / "logs")
    bundled_dictionary_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent / "assets" / "dictionaries"
    )
    user_dictionary_dir: Path = field(default_factory=lambda: _default_home_dir() / "dictionary-packs")
    project_dir: Path = field(default_factory=_resource_root)

    @property
    def static_dir(self) -> Path:
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            meipass = Path(getattr(sys, "_MEIPASS"))
            candidates.extend(
                [
                    meipass / "app" / "static",
                    meipass / "static",
                ]
            )
        candidates.extend(
            [
                Path(__file__).resolve().parent / "static",
                Path(__file__).resolve().parent.parent / "app" / "static",
            ]
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return Path(__file__).resolve().parent / "static"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def desktop_mode(self) -> bool:
        return self.app_mode == "desktop"

    @property
    def show_auth_ui(self) -> bool:
        return not self.desktop_mode

    @property
    def show_extension_ui(self) -> bool:
        return not self.desktop_mode

    @property
    def desktop_base_url(self) -> str:
        return f"http://{self.desktop_host}:{self.desktop_port}"

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.app_home_dir,
            self.app_data_dir,
            self.app_cache_dir,
            self.app_book_cache_dir,
            self.app_log_dir,
            self.user_dictionary_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
