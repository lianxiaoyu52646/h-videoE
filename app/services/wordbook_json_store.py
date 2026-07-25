"""Load curated wordbook JSON from disk (not Neon/Postgres)."""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

from app.services.wordbook_entry_format import normalize_catalog_entry

CATALOG_DIR = Path(__file__).resolve().parent.parent / "assets" / "curated"

_lock = threading.Lock()
_cache: dict[str, list[dict]] = {}


def asset_path(asset_file: str) -> Path:
    return CATALOG_DIR / asset_file


def load_entries(asset_file: str) -> list[dict]:
    """Return normalized entries for a curated JSON wordbook (cached)."""
    key = (asset_file or "").replace("\\", "/").strip()
    if not key:
        return []
    with _lock:
        if key in _cache:
            return _cache[key]
    path = asset_path(key)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("entries") if isinstance(payload, dict) else payload
    entries = [normalize_catalog_entry(entry) for entry in (raw or [])]
    with _lock:
        _cache[key] = entries
    return entries


def slice_entries(asset_file: str, offset: int, limit: int) -> tuple[list[dict], int]:
    entries = load_entries(asset_file)
    total = len(entries)
    start = max(0, min(int(offset), total))
    end = max(start, min(start + max(0, int(limit)), total))
    return entries[start:end], total


@lru_cache(maxsize=1)
def manifest_asset_by_key() -> dict[str, str]:
    path = CATALOG_DIR / "wordbook_catalog.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    return {item["key"]: item.get("asset_file") or "" for item in items}
