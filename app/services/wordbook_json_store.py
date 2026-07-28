"""Load curated wordbook JSON from disk (not Neon/Postgres).

Keeps an LRU of parsed books so Render free-tier memory is not blown by
loading every catalog JSON at once.

Hot path: cache RAW entries; normalize only the requested slice.
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from app.services.wordbook_entry_format import normalize_catalog_entry

CATALOG_DIR = Path(__file__).resolve().parent.parent / "assets" / "curated"

_lock = threading.Lock()
# asset_key -> raw entry list (dicts as stored in JSON)
_cache: "OrderedDict[str, list]" = OrderedDict()
_count_cache: dict[str, int] = {}
_MAX_CACHED_BOOKS = 6


def asset_path(asset_file: str) -> Path:
    return CATALOG_DIR / asset_file


def _normalize_key(asset_file: str) -> str:
    return (asset_file or "").replace("\\", "/").strip()


def entry_count(asset_file: str) -> int:
    """Word count without retaining a full parse when possible."""
    key = _normalize_key(asset_file)
    if not key:
        return 0
    with _lock:
        if key in _count_cache:
            return _count_cache[key]
        if key in _cache:
            n = len(_cache[key])
            _count_cache[key] = n
            return n
    path = asset_path(key)
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("entries") if isinstance(payload, dict) else payload
    n = len(raw or [])
    with _lock:
        _count_cache[key] = n
    return n


def load_entries_raw(asset_file: str) -> list:
    """Return raw JSON entry dicts (LRU-cached). No per-entry normalize."""
    key = _normalize_key(asset_file)
    if not key:
        return []
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    path = asset_path(key)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("entries") if isinstance(payload, dict) else payload
    entries = list(raw or [])
    with _lock:
        _cache[key] = entries
        _count_cache[key] = len(entries)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_CACHED_BOOKS:
            _cache.popitem(last=False)
    return entries


def load_entries(asset_file: str) -> list[dict]:
    """Legacy helper: normalized full list (avoid on hot scroll path)."""
    return [normalize_catalog_entry(e if isinstance(e, dict) else {}) for e in load_entries_raw(asset_file)]


def slice_entries(asset_file: str, offset: int, limit: int) -> tuple[list[dict], int]:
    """Return only the requested page, normalized. O(page) not O(book)."""
    entries = load_entries_raw(asset_file)
    total = len(entries)
    start = max(0, min(int(offset), total))
    end = max(start, min(start + max(0, int(limit)), total))
    page = [
        normalize_catalog_entry(e if isinstance(e, dict) else {})
        for e in entries[start:end]
    ]
    return page, total


def entry_at(asset_file: str, offset: int) -> dict | None:
    page, total = slice_entries(asset_file, offset, 1)
    if not page or offset < 0 or offset >= total:
        return None
    return page[0]


@lru_cache(maxsize=1)
def manifest_asset_by_key() -> dict[str, str]:
    path = CATALOG_DIR / "wordbook_catalog.json"
    if not path.exists():
        return {}
    items = json.loads(path.read_text(encoding="utf-8"))
    return {item["key"]: item.get("asset_file") or "" for item in items}
