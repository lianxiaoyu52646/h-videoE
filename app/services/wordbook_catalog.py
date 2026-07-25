from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, func, select
from sqlalchemy.exc import OperationalError

from app import crud, models, security
from app.services.wordbook_entry_format import normalize_catalog_entry


logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).resolve().parent.parent / "assets" / "curated" / "wordbook_catalog.json"


def _current_user_id() -> int:
    return security.get_current_user_id(required=False) or 1

def _load_manifest() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def load_manifest() -> list[dict]:
    return _load_manifest()


def _resolve_asset_path(asset_file: str) -> Path:
    return CATALOG_PATH.parent / asset_file


def _apply_manifest_item(row: models.WordBookCatalog, item: dict) -> bool:
    changed = False
    updates = {
        "provider": item.get("provider") or "github",
        "name": item.get("name") or row.name or "",
        "description": item.get("description") or row.description or "",
        "source_name": item.get("source_name") or row.source_name,
        "repo_url": item.get("repo_url") or row.repo_url or "",
        "raw_url": item.get("raw_url") or row.raw_url or "",
        "asset_file": item.get("asset_file") or row.asset_file or "",
        "entry_count": int(item.get("entry_count") or 0),
    }
    for field, value in updates.items():
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True
    return changed


def ensure_catalog(session: Session) -> list[models.WordBookCatalog]:
    user_id = _current_user_id()
    manifest = _load_manifest()
    now = datetime.utcnow()
    changed = False
    with session.no_autoflush:
        for item in manifest:
            row = session.exec(
                select(models.WordBookCatalog).where(
                    models.WordBookCatalog.user_id == user_id,
                    models.WordBookCatalog.key == item["key"],
                )
            ).first()
            if not row:
                row = models.WordBookCatalog(user_id=user_id, key=item["key"])
                changed = True
            if _apply_manifest_item(row, item):
                row.updated_at = now
                changed = True
            session.add(row)
    if changed:
        session.commit()
    manifest_keys = {item["key"] for item in manifest}
    existing_rows = session.exec(
        select(models.WordBookCatalog).where(models.WordBookCatalog.user_id == user_id)
    ).all()
    for row in existing_rows:
        if row.key not in manifest_keys:
            session.delete(row)
            changed = True
    if changed:
        session.commit()
    return session.exec(
        select(models.WordBookCatalog)
        .where(models.WordBookCatalog.user_id == user_id)
        .order_by(models.WordBookCatalog.name.asc())
    ).all()


def _repair_stale_installations(session: Session, user_id: int) -> None:
    rows = session.exec(
        select(models.WordBookCatalog).where(models.WordBookCatalog.user_id == user_id)
    ).all()
    changed = False
    now = datetime.utcnow()
    for row in rows:
        if not row.installed_wordbook_id:
            continue
        if crud.get_wordbook(session, row.installed_wordbook_id, user_id=user_id):
            continue
        row.installed_wordbook_id = None
        row.installed_at = None
        row.updated_at = now
        session.add(row)
        changed = True
    if changed:
        session.commit()


def list_catalog(session: Session) -> list[models.WordBookCatalog]:
    user_id = _current_user_id()
    try:
        rows = ensure_catalog(session)
    except OperationalError:
        session.rollback()
        rows = session.exec(
            select(models.WordBookCatalog)
            .where(models.WordBookCatalog.user_id == user_id)
            .order_by(models.WordBookCatalog.name.asc())
        ).all()
        if not rows:
            raise
    _repair_stale_installations(session, user_id)
    # Auto-persist all bundled wordbooks — users no longer need manual install.
    from app.config import settings

    if settings.auto_install_wordbooks:
        ensure_all_catalog_installed(session, user_id=user_id)
    return session.exec(
        select(models.WordBookCatalog)
        .where(models.WordBookCatalog.user_id == user_id)
        .order_by(models.WordBookCatalog.name.asc())
    ).all()


def _entry_count_for_wordbook(session: Session, wordbook_id: int) -> int:
    return int(
        session.exec(
            select(func.count(models.WordBookEntry.id)).where(
                models.WordBookEntry.wordbook_id == wordbook_id
            )
        ).one()
        or 0
    )


def install_catalog_wordbook(
    session: Session,
    catalog_key: str,
    *,
    user_id: int | None = None,
    force: bool = False,
) -> tuple[models.WordBookCatalog, models.WordBook, int]:
    uid = user_id if user_id is not None else _current_user_id()
    token = security.set_current_user(uid)
    try:
        ensure_catalog(session)
        row = session.exec(
            select(models.WordBookCatalog).where(
                models.WordBookCatalog.user_id == uid,
                models.WordBookCatalog.key == catalog_key,
            )
        ).first()
        if not row:
            raise KeyError("catalog wordbook not found")

        asset_path = _resolve_asset_path(row.asset_file)
        if not asset_path.exists():
            raise FileNotFoundError(asset_path)
        payload = json.loads(asset_path.read_text(encoding="utf-8"))
        entries = [normalize_catalog_entry(entry) for entry in (payload.get("entries") or [])]
        expected = len(entries)

        wordbook = None
        if row.installed_wordbook_id:
            wordbook = crud.get_wordbook(session, row.installed_wordbook_id, user_id=uid)

        if not wordbook:
            wordbook = crud.create_wordbook(
                session,
                row.name,
                description=row.description,
                language="en",
                source_name=row.source_name or row.key,
                user_id=uid,
            )
        else:
            wordbook.description = row.description or wordbook.description
            wordbook.source_name = row.source_name or wordbook.source_name
            session.add(wordbook)
            session.commit()
            session.refresh(wordbook)

        current = _entry_count_for_wordbook(session, wordbook.id)
        if not force and expected > 0 and current >= int(expected * 0.98):
            row.installed_wordbook_id = wordbook.id
            row.installed_at = row.installed_at or datetime.utcnow()
            row.updated_at = datetime.utcnow()
            row.entry_count = current
            session.add(row)
            session.commit()
            session.refresh(row)
            session.refresh(wordbook)
            return row, wordbook, current

        imported_count = crud.add_wordbook_entries(session, wordbook.id, entries)
        row.installed_wordbook_id = wordbook.id
        row.installed_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        row.entry_count = _entry_count_for_wordbook(session, wordbook.id)
        session.add(row)
        session.commit()
        session.refresh(row)
        session.refresh(wordbook)
        return row, wordbook, imported_count
    finally:
        security.reset_current_user(token)


def ensure_all_catalog_installed(
    session: Session,
    *,
    user_id: int | None = None,
) -> dict:
    """Install every bundled KyleBing wordbook into SQLite for the user."""
    uid = user_id if user_id is not None else _current_user_id()
    ensure_catalog(session)
    _repair_stale_installations(session, uid)
    rows = session.exec(
        select(models.WordBookCatalog).where(models.WordBookCatalog.user_id == uid)
    ).all()
    installed = 0
    total_entries = 0
    for row in rows:
        try:
            _, wordbook, _count = install_catalog_wordbook(session, row.key, user_id=uid)
            total_entries += _entry_count_for_wordbook(session, wordbook.id)
            installed += 1
        except Exception:
            logger.exception("failed to preinstall wordbook key=%s user=%s", row.key, uid)
    logger.info(
        "bundled wordbooks ready user=%s books=%s entries=%s",
        uid,
        installed,
        total_entries,
    )
    return {
        "user_id": uid,
        "books": installed,
        "entries": total_entries,
    }


def ensure_bundled_wordbooks_for_all_users(session: Session) -> list[dict]:
    users = session.exec(select(models.User).where(models.User.is_active == True)).all()  # noqa: E712
    if not users:
        # Desktop / first boot may create default user elsewhere.
        return []
    results = []
    for user in users:
        results.append(ensure_all_catalog_installed(session, user_id=user.id))
    return results
