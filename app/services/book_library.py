from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path

import httpx
from sqlmodel import Session, select
from sqlalchemy.exc import OperationalError

from app import crud, models, security
from app.config import settings


CATALOG_PATHS = [
    Path(__file__).resolve().parent.parent / "assets" / "curated" / "gutenberg_100.json",
    Path(__file__).resolve().parent.parent / "assets" / "curated" / "book_catalog.json",
]
BUNDLED_BOOKS_DIR = Path(__file__).resolve().parent.parent / "assets" / "books" / "gutenberg"
GUTENBERG_START_RE = re.compile(
    r"\*\*\*\s*START OF (?:THIS|THE) PROJECT GUTENBERG EBOOK.*?\*\*\*",
    re.IGNORECASE | re.DOTALL,
)
GUTENBERG_END_RE = re.compile(
    r"\*\*\*\s*END OF (?:THIS|THE) PROJECT GUTENBERG EBOOK.*",
    re.IGNORECASE | re.DOTALL,
)

_import_lock_guard = threading.Lock()
_import_locks: dict[tuple[int, str], threading.Lock] = {}


def _book_import_lock(user_id: int, book_key: str) -> threading.Lock:
    key = (user_id, book_key)
    with _import_lock_guard:
        lock = _import_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _import_locks[key] = lock
        return lock


def _current_user_id() -> int:
    return security.get_current_user_id(required=False) or 1


def _load_manifest() -> list[dict]:
    for path in CATALOG_PATHS:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    return []


def _bundled_asset_path(row: models.LibraryBook, item: dict | None = None) -> Path | None:
    """Prefer pre-shipped Gutenberg txt under app/assets/books/gutenberg/."""
    asset = None
    if item:
        asset = item.get("asset_file")
        gid = item.get("gutenberg_id")
    else:
        asset = None
        gid = None
        if row.key.startswith("pg_"):
            try:
                gid = int(row.key.split("_", 1)[1])
            except Exception:
                gid = None
    candidates: list[Path] = []
    if asset:
        candidates.append(BUNDLED_BOOKS_DIR / str(asset))
    if gid:
        candidates.append(BUNDLED_BOOKS_DIR / f"{gid}.txt")
    # legacy android-style names
    if row.key:
        candidates.append(BUNDLED_BOOKS_DIR / f"{row.key}.txt")
    for path in candidates:
        if path.exists() and path.stat().st_size > 500:
            return path
    return None


def _read_bundled_or_cached_text(row: models.LibraryBook, item: dict | None = None) -> str | None:
    bundled = _bundled_asset_path(row, item)
    if bundled:
        return bundled.read_text(encoding="utf-8", errors="replace")
    return _read_cached_text(row)


def _book_cache_dir() -> Path:
    return settings.app_book_cache_dir


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_book_text(text: str) -> str:
    content = text.replace("\r\n", "\n").replace("\r", "\n")
    start_match = GUTENBERG_START_RE.search(content)
    if start_match:
        content = content[start_match.end() :]
    end_match = GUTENBERG_END_RE.search(content)
    if end_match:
        content = content[: end_match.start()]
    return content.strip()


def _decode_book_bytes(content: bytes, declared_encoding: str | None) -> str:
    candidates: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for encoding in (
        declared_encoding,
        "utf-8-sig",
        "utf-8",
        "gb18030",
        "cp1252",
        "latin-1",
    ):
        enc = (encoding or "").strip().lower()
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            text = content.decode(enc)
        except Exception:
            continue
        score = (
            text.count("\ufffd"),
            -text[:5000].count("Project Gutenberg"),
        )
        candidates.append((score[0], score[1], text))
    if not candidates:
        return content.decode("utf-8", errors="replace")
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _apply_manifest_item(row: models.LibraryBook, item: dict) -> bool:
    changed = False
    updates = {
        "provider": item.get("provider") or "github",
        "title": item.get("title") or row.title or "",
        "author": item.get("author") or row.author or "",
        "description": item.get("description") or row.description or "",
        "language": item.get("language") or row.language or "en",
        "repo_url": item.get("repo_url") or row.repo_url or "",
        "raw_url": item.get("raw_url") or row.raw_url or "",
        "tags": list(item.get("tags") or row.tags or []),
    }
    for field, value in updates.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    return changed


def ensure_catalog(session: Session) -> list[models.LibraryBook]:
    user_id = _current_user_id()
    manifest = _load_manifest()
    now = datetime.utcnow()
    changed = False
    with session.no_autoflush:
        for item in manifest:
            row = session.exec(
                select(models.LibraryBook).where(
                    models.LibraryBook.user_id == user_id,
                    models.LibraryBook.key == item["key"],
                )
            ).first()
            if not row:
                row = models.LibraryBook(user_id=user_id, key=item["key"])
                changed = True
            if _apply_manifest_item(row, item):
                row.updated_at = now
                changed = True
            session.add(row)
    if changed:
        session.commit()
    # Only surface books from the active curated manifest (hide legacy catalog rows).
    keys = [item["key"] for item in manifest if item.get("key")]
    if not keys:
        return []
    rows = session.exec(
        select(models.LibraryBook)
        .where(
            models.LibraryBook.user_id == user_id,
            models.LibraryBook.key.in_(keys),
        )
        .order_by(models.LibraryBook.title.asc())
    ).all()
    return rows


def list_books(session: Session) -> list[models.LibraryBook]:
    user_id = _current_user_id()
    try:
        return ensure_catalog(session)
    except OperationalError:
        session.rollback()
        manifest = _load_manifest()
        keys = [item["key"] for item in manifest if item.get("key")]
        if not keys:
            raise
        rows = session.exec(
            select(models.LibraryBook)
            .where(
                models.LibraryBook.user_id == user_id,
                models.LibraryBook.key.in_(keys),
            )
            .order_by(models.LibraryBook.title.asc())
        ).all()
        if rows:
            return rows
        raise


def _read_cached_text(row: models.LibraryBook) -> str | None:
    if not row.cache_path:
        return None
    path = Path(row.cache_path)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _download_book_text(row: models.LibraryBook) -> str:
    resp = httpx.get(row.raw_url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return _decode_book_bytes(resp.content, resp.encoding)


def import_book(
    session: Session,
    book_key: str,
) -> tuple[models.LibraryBook, models.ReadingDocument, bool]:
    user_id = _current_user_id()
    with _book_import_lock(user_id, book_key):
        return _import_book_locked(session, book_key, user_id=user_id)


def _import_book_locked(
    session: Session,
    book_key: str,
    *,
    user_id: int,
) -> tuple[models.LibraryBook, models.ReadingDocument, bool]:
    ensure_catalog(session)
    row = session.exec(
        select(models.LibraryBook).where(
            models.LibraryBook.user_id == user_id,
            models.LibraryBook.key == book_key,
        )
    ).first()
    if not row:
        raise KeyError("library book not found")

    if row.reading_document_id:
        existing = crud.get_reading(session, row.reading_document_id, user_id=user_id)
        if existing:
            if not existing.edition_id:
                text = _read_bundled_or_cached_text(
                    row,
                    next((m for m in _load_manifest() if m.get("key") == book_key), None),
                )
                if text:
                    text = _normalize_book_text(text)
                    sha = row.cache_sha256 or _sha256_text(text)
                    try:
                        from app.services import book_shared

                        book_shared.attach_edition_to_document(
                            session,
                            existing,
                            book_key=row.key,
                            content_sha256=sha,
                            author=row.author or "",
                        )
                        session.refresh(existing)
                    except Exception:
                        pass
            elif (existing.block_count or 0) > 0:
                try:
                    from app.services import book_shared

                    book_shared.hydrate_document_range(
                        session,
                        existing.id,
                        0,
                        min(79, (existing.block_count or 1) - 1),
                    )
                except Exception:
                    pass
            return row, existing, False
        row.reading_document_id = None
        session.add(row)
        session.commit()
        session.refresh(row)

    text = None
    manifest_item = next((m for m in _load_manifest() if m.get("key") == book_key), None)
    text = _read_bundled_or_cached_text(row, manifest_item)
    if text:
        text = _normalize_book_text(text)
        bundled = _bundled_asset_path(row, manifest_item)
        if bundled and not row.cache_path:
            row.cache_path = str(bundled)
            row.cache_sha256 = _sha256_text(text)
            row.cache_bytes = bundled.stat().st_size
            row.cache_status = "bundled"
            row.last_synced_at = datetime.utcnow()
    if not text:
        raw_text = _download_book_text(row)
        text = _normalize_book_text(raw_text)
        cache_dir = _book_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{row.key}.txt"
        cache_path.write_text(text, encoding="utf-8")
        row.cache_path = str(cache_path)
        row.cache_sha256 = _sha256_text(text)
        row.cache_bytes = cache_path.stat().st_size
        row.cache_status = "cached"
        row.last_error = None
        row.last_synced_at = datetime.utcnow()
    else:
        if row.cache_path:
            cache_path = Path(row.cache_path)
            row.cache_status = row.cache_status or "cached"
            row.cache_bytes = cache_path.stat().st_size if cache_path.exists() else len(text.encode("utf-8"))
            row.cache_sha256 = row.cache_sha256 or _sha256_text(text)
            row.last_error = None
            row.last_synced_at = row.last_synced_at or datetime.utcnow()

    doc = crud.create_reading(
        session,
        row.title,
        text,
        source_type="gutenberg-book" if (row.provider == "gutenberg" or row.key.startswith("pg_")) else "github-book",
        source_url=row.repo_url or row.raw_url,
        source_filename=f"{row.key}.txt",
        user_id=user_id,
    )
    content_sha = row.cache_sha256 or _sha256_text(text)
    try:
        from app.services import book_shared

        book_shared.attach_edition_to_document(
            session,
            doc,
            book_key=row.key,
            content_sha256=content_sha,
            author=row.author or "",
        )
        session.refresh(doc)
    except Exception:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("attach shared book edition failed for %s", row.key)
    row.reading_document_id = doc.id
    row.imported_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    session.refresh(doc)
    return row, doc, True


def _get_book_row(session: Session, book_key: str, *, user_id: int) -> models.LibraryBook:
    ensure_catalog(session)
    row = session.exec(
        select(models.LibraryBook).where(
            models.LibraryBook.user_id == user_id,
            models.LibraryBook.key == book_key,
        )
    ).first()
    if not row:
        raise KeyError("library book not found")
    return row


def refresh_book_cache(session: Session, book_key: str) -> models.LibraryBook:
    user_id = _current_user_id()
    with _book_import_lock(user_id, book_key):
        row = _get_book_row(session, book_key, user_id=user_id)
        if row.cache_path:
            path = Path(row.cache_path)
            if path.exists():
                path.unlink()
        row.cache_path = None
        row.cache_sha256 = None
        row.cache_bytes = 0
        row.cache_status = "pending"
        row.last_error = None
        raw_text = _download_book_text(row)
        text = _normalize_book_text(raw_text)
        cache_dir = _book_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{row.key}.txt"
        cache_path.write_text(text, encoding="utf-8")
        row.cache_path = str(cache_path)
        row.cache_sha256 = _sha256_text(text)
        row.cache_bytes = cache_path.stat().st_size
        row.cache_status = "cached"
        row.last_synced_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def unlink_book(
    session: Session,
    book_key: str,
    *,
    delete_reading: bool = False,
) -> models.LibraryBook:
    user_id = _current_user_id()
    row = _get_book_row(session, book_key, user_id=user_id)
    if delete_reading and row.reading_document_id:
        crud.delete_reading(session, row.reading_document_id, user_id=user_id)
    row.reading_document_id = None
    row.imported_at = None
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def reimport_book(
    session: Session,
    book_key: str,
) -> tuple[models.LibraryBook, models.ReadingDocument, bool]:
    user_id = _current_user_id()
    with _book_import_lock(user_id, book_key):
        row = _get_book_row(session, book_key, user_id=user_id)
        if row.reading_document_id:
            crud.delete_reading(session, row.reading_document_id, user_id=user_id)
            row.reading_document_id = None
            row.imported_at = None
            session.add(row)
            session.commit()
            session.refresh(row)
        return _import_book_locked(session, book_key, user_id=user_id)


def mark_failed(session: Session, book_key: str, message: str) -> None:
    user_id = _current_user_id()
    row = session.exec(
        select(models.LibraryBook).where(
            models.LibraryBook.user_id == user_id,
            models.LibraryBook.key == book_key,
        )
    ).first()
    if not row:
        return
    row.cache_status = "failed"
    row.last_error = (message or "").strip() or "unknown error"
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
