"""Shared book EN/ZH storage — one edition per book_key+content, reused by all users."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlmodel import Session, func, or_, select

from app import crud, models
from app.services import reading_cache
from app.services.text_hash import text_hash

logger = logging.getLogger(__name__)

PARAGRAPH_INSERT_BATCH = 400


def _utc_now() -> datetime:
    return datetime.utcnow()


def refresh_edition_progress(session: Session, edition_id: int) -> models.BookEdition | None:
    edition = session.get(models.BookEdition, edition_id)
    if not edition:
        return None
    translated = int(
        session.exec(
            select(func.count(models.BookParagraph.id)).where(
                models.BookParagraph.edition_id == edition_id,
                or_(
                    func.length(func.trim(models.BookParagraph.zh_text)) > 0,
                    models.BookParagraph.zh_source == "skip",
                ),
            )
        ).one()
        or 0
    )
    total = int(edition.block_count or 0)
    edition.translated_blocks = translated
    if total > 0 and translated >= total:
        edition.translate_status = "done"
    elif translated > 0:
        edition.translate_status = "partial"
    else:
        edition.translate_status = "pending"
    edition.updated_at = _utc_now()
    session.add(edition)
    return edition


def get_or_create_edition(
    session: Session,
    *,
    book_key: str,
    content_sha256: str,
    title: str = "",
    author: str = "",
    source_url: str | None = None,
    block_count: int = 0,
) -> models.BookEdition:
    key = (book_key or "").strip()
    sha = (content_sha256 or "").strip()
    if not key or not sha:
        raise ValueError("book_key and content_sha256 are required")

    row = session.exec(
        select(models.BookEdition).where(
            models.BookEdition.book_key == key,
            models.BookEdition.content_sha256 == sha,
        )
    ).first()
    if row:
        changed = False
        if title and row.title != title:
            row.title = title
            changed = True
        if author and row.author != author:
            row.author = author
            changed = True
        if source_url and row.source_url != source_url:
            row.source_url = source_url
            changed = True
        if block_count and row.block_count != block_count:
            row.block_count = block_count
            changed = True
        if changed:
            row.updated_at = _utc_now()
            session.add(row)
            session.commit()
            session.refresh(row)
        return row

    row = models.BookEdition(
        book_key=key,
        content_sha256=sha,
        title=title or key,
        author=author or "",
        source_url=source_url,
        block_count=block_count,
        translate_status="pending",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _existing_paragraph_count(session: Session, edition_id: int) -> int:
    return int(
        session.exec(
            select(func.count(models.BookParagraph.id)).where(
                models.BookParagraph.edition_id == edition_id
            )
        ).one()
        or 0
    )


def sync_paragraphs_from_document(session: Session, edition: models.BookEdition, doc_id: int) -> int:
    """Ensure edition has EN rows; fill ZH from this doc when shared ZH is empty."""
    blocks = crud.get_reading_blocks(session, doc_id)
    if not blocks:
        return 0

    existing = _existing_paragraph_count(session, edition.id)
    created = 0
    if existing == 0:
        for start in range(0, len(blocks), PARAGRAPH_INSERT_BATCH):
            batch = blocks[start : start + PARAGRAPH_INSERT_BATCH]
            rows = []
            for block in batch:
                zh = (block.translation or "").strip() or None
                rows.append(
                    models.BookParagraph(
                        edition_id=edition.id,
                        order_index=block.order_index,
                        en_text=block.text,
                        en_hash=block.text_hash or text_hash(block.text),
                        zh_text=zh,
                        zh_source="user" if zh else None,
                        translated_at=_utc_now() if zh else None,
                    )
                )
            session.add_all(rows)
            session.commit()
            created += len(rows)
        # Preserve full-book count when the user doc is still sparsely materialized.
        edition.block_count = max(int(edition.block_count or 0), len(blocks))
        session.add(edition)
        session.commit()
        refresh_edition_progress(session, edition.id)
        session.commit()
        return created

    # Merge: push user ZH into empty shared rows; hydrate will do the reverse.
    paras = {
        p.order_index: p
        for p in session.exec(
            select(models.BookParagraph).where(models.BookParagraph.edition_id == edition.id)
        ).all()
    }
    changed = 0
    for block in blocks:
        zh = (block.translation or "").strip()
        if not zh:
            continue
        para = paras.get(block.order_index)
        if not para:
            continue
        if (para.zh_text or "").strip():
            continue
        para.zh_text = zh
        para.zh_source = para.zh_source or "user"
        para.translated_at = _utc_now()
        para.updated_at = _utc_now()
        session.add(para)
        changed += 1
    if changed:
        session.commit()
        refresh_edition_progress(session, edition.id)
        session.commit()
    return changed


def attach_edition_to_document(
    session: Session,
    doc: models.ReadingDocument,
    *,
    book_key: str,
    content_sha256: str,
    author: str = "",
    sync_paragraphs: bool = True,
    hydrate_blocks: int = 80,
) -> models.BookEdition:
    edition = get_or_create_edition(
        session,
        book_key=book_key,
        content_sha256=content_sha256,
        title=doc.title or book_key,
        author=author,
        source_url=doc.source_url,
        block_count=doc.block_count or 0,
    )
    # Full-book sync/hydrate on free Render often exceeds the proxy timeout → 502.
    if sync_paragraphs and _existing_paragraph_count(session, edition.id) == 0:
        sync_paragraphs_from_document(session, edition, doc.id)
    session.refresh(edition)
    if (edition.translated_blocks or 0) > 0 and hydrate_blocks > 0:
        last = max((doc.block_count or 1) - 1, 0)
        hydrate_document_range(
            session,
            doc.id,
            0,
            min(hydrate_blocks - 1, last),
            edition_id=edition.id,
        )
    doc.book_key = book_key
    doc.edition_id = edition.id
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return edition


def upsert_paragraph_translation(
    session: Session,
    edition_id: int,
    order_index: int,
    en_text: str,
    zh_text: str,
    *,
    source: str = "youdao",
) -> bool:
    zh = (zh_text or "").strip()
    if not zh:
        return False
    para = session.exec(
        select(models.BookParagraph).where(
            models.BookParagraph.edition_id == edition_id,
            models.BookParagraph.order_index == order_index,
        )
    ).first()
    now = _utc_now()
    if not para:
        para = models.BookParagraph(
            edition_id=edition_id,
            order_index=order_index,
            en_text=en_text or "",
            en_hash=text_hash(en_text),
            zh_text=zh,
            zh_source=source,
            translated_at=now,
        )
        session.add(para)
        return True
    if (para.zh_text or "").strip() == zh:
        return False
    was_empty = not (para.zh_text or "").strip()
    para.zh_text = zh
    para.zh_source = source
    para.translated_at = now
    para.updated_at = now
    if en_text and not (para.en_text or "").strip():
        para.en_text = en_text
        para.en_hash = text_hash(en_text)
    session.add(para)
    return was_empty


def save_block_translations_to_shared(
    session: Session,
    doc_id: int,
    blocks: list[models.ReadingBlock],
    translations: list[str],
    *,
    source: str = "youdao",
) -> int:
    doc = session.get(models.ReadingDocument, doc_id)
    if not doc or not doc.edition_id:
        return 0
    saved = 0
    for block, tr in zip(blocks, translations):
        if upsert_paragraph_translation(
            session,
            doc.edition_id,
            block.order_index,
            block.text,
            tr,
            source=source,
        ):
            saved += 1
    if saved:
        refresh_edition_progress(session, doc.edition_id)
    return saved


def hydrate_document_range(
    session: Session,
    doc_id: int,
    start_block: int,
    end_block: int,
    *,
    edition_id: int | None = None,
) -> int:
    """Copy shared ZH into the user's reading blocks for a range."""
    doc = session.get(models.ReadingDocument, doc_id)
    if not doc:
        return 0
    eid = edition_id or doc.edition_id
    if not eid:
        return 0

    paras = session.exec(
        select(models.BookParagraph).where(
            models.BookParagraph.edition_id == eid,
            models.BookParagraph.order_index >= start_block,
            models.BookParagraph.order_index <= end_block,
            models.BookParagraph.zh_text.is_not(None),
            func.length(func.trim(models.BookParagraph.zh_text)) > 0,
        )
    ).all()
    if not paras:
        return 0
    by_order = {p.order_index: (p.zh_text or "").strip() for p in paras}

    applied = 0
    for block in crud.get_reading_blocks_in_range(session, doc_id, start_block, end_block):
        if (block.translation or "").strip():
            continue
        zh = by_order.get(block.order_index)
        if not zh:
            continue
        block.translation = zh
        session.add(block)
        reading_cache.patch_block_translation(doc_id, block.order_index, zh)
        applied += 1
    if applied:
        crud.increment_translated_blocks(session, doc_id, applied)
        session.commit()
    return applied


def list_missing_paragraphs(
    session: Session,
    *,
    book_key: str | None = None,
    edition_id: int | None = None,
    limit: int = 100,
) -> list[models.BookParagraph]:
    missing_zh = or_(
        models.BookParagraph.zh_text.is_(None),
        func.length(func.trim(models.BookParagraph.zh_text)) == 0,
    )
    stmt = select(models.BookParagraph).where(
        missing_zh,
        or_(
            models.BookParagraph.zh_source.is_(None),
            models.BookParagraph.zh_source != "skip",
        ),
        func.length(func.trim(models.BookParagraph.en_text)) > 0,
    )
    if edition_id is not None:
        stmt = stmt.where(models.BookParagraph.edition_id == edition_id)
    elif book_key:
        editions = session.exec(
            select(models.BookEdition.id).where(models.BookEdition.book_key == book_key)
        ).all()
        if not editions:
            return []
        stmt = stmt.where(models.BookParagraph.edition_id.in_(list(editions)))
    stmt = stmt.order_by(
        models.BookParagraph.edition_id.asc(),
        models.BookParagraph.order_index.asc(),
    ).limit(max(1, min(limit, 500)))
    return list(session.exec(stmt).all())


def edition_translation_stats(session: Session) -> dict:
    """Aggregate shared-book translation progress for UI scan."""
    rows = session.exec(select(models.BookEdition)).all()
    total = len(rows)
    done = sum(1 for r in rows if (r.translate_status or "") == "done")
    partial = sum(1 for r in rows if (r.translate_status or "") == "partial")
    pending_only = sum(1 for r in rows if (r.translate_status or "pending") == "pending")
    not_done = total - done
    return {
        "total_books": total,
        "done_books": done,
        "partial_books": partial,
        "pending_books": not_done,
        "pending_only": pending_only,
    }


def list_editions_needing_work(
    session: Session,
    *,
    book_key: str | None = None,
    prefer_book_key: str | None = None,
    limit: int = 20,
) -> list[models.BookEdition]:
    """Editions that are not fully translated (skip done). Stable order; prefer resume key first."""
    stmt = select(models.BookEdition).where(
        or_(
            models.BookEdition.translate_status.is_(None),
            models.BookEdition.translate_status != "done",
        )
    )
    if book_key:
        stmt = stmt.where(models.BookEdition.book_key == book_key)
    stmt = stmt.order_by(models.BookEdition.book_key.asc()).limit(max(1, min(limit, 100)))
    rows = list(session.exec(stmt).all())
    out: list[models.BookEdition] = []
    for row in rows:
        if row.translate_status == "done":
            continue
        total = int(row.block_count or 0)
        done = int(row.translated_blocks or 0)
        if total > 0 and done >= total:
            refresh_edition_progress(session, row.id)
            continue
        out.append(row)
    session.commit()
    prefer = (prefer_book_key or "").strip()
    if prefer and len(out) > 1:
        preferred = [r for r in out if r.book_key == prefer]
        rest = [r for r in out if r.book_key != prefer]
        out = preferred + rest
    return out


def get_or_create_translate_checkpoint(session: Session) -> models.BookTranslateCheckpoint:
    row = session.exec(select(models.BookTranslateCheckpoint).order_by(models.BookTranslateCheckpoint.id.asc())).first()
    if row:
        return row
    row = models.BookTranslateCheckpoint(status="idle", message="")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def save_translate_checkpoint(
    session: Session,
    *,
    status: str | None = None,
    current_book_key: str | None = None,
    current_edition_id: int | None = None,
    current_order_index: int | None = None,
    books_total: int | None = None,
    books_finished: int | None = None,
    translated_paragraphs: int | None = None,
    failed_paragraphs: int | None = None,
    message: str | None = None,
    job_id: int | None = None,
    clear_cursor: bool = False,
) -> models.BookTranslateCheckpoint:
    row = get_or_create_translate_checkpoint(session)
    if status is not None:
        row.status = status
        if status == "running" and row.started_at is None:
            row.started_at = _utc_now()
        if status in {"done", "paused", "idle"}:
            if status == "done":
                row.finished_at = _utc_now()
            elif status == "running":
                row.finished_at = None
    if clear_cursor:
        row.current_book_key = None
        row.current_edition_id = None
        row.current_order_index = 0
    else:
        if current_book_key is not None:
            row.current_book_key = current_book_key
        if current_edition_id is not None:
            row.current_edition_id = current_edition_id
        if current_order_index is not None:
            row.current_order_index = int(current_order_index)
    if books_total is not None:
        row.books_total = int(books_total)
    if books_finished is not None:
        row.books_finished = int(books_finished)
    if translated_paragraphs is not None:
        row.translated_paragraphs = int(translated_paragraphs)
    if failed_paragraphs is not None:
        row.failed_paragraphs = int(failed_paragraphs)
    if message is not None:
        row.message = message
    if job_id is not None:
        row.job_id = job_id
    row.updated_at = _utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def checkpoint_to_dict(row: models.BookTranslateCheckpoint | None) -> dict:
    if not row:
        return {
            "status": "idle",
            "resumable": False,
            "current_book_key": None,
            "current_order_index": 0,
            "books_total": 0,
            "books_finished": 0,
            "translated_paragraphs": 0,
            "failed_paragraphs": 0,
            "percent": 0,
            "message": "",
        }
    total = int(row.books_total or 0)
    finished = int(row.books_finished or 0)
    percent = 100 if total <= 0 and row.status == "done" else (
        max(0, min(100, int(finished / max(total, 1) * 100)))
    )
    resumable = row.status in {"paused", "running"}
    return {
        "status": row.status,
        "resumable": resumable,
        "current_book_key": row.current_book_key,
        "current_edition_id": row.current_edition_id,
        "current_order_index": row.current_order_index,
        "books_total": total,
        "books_finished": finished,
        "translated_paragraphs": int(row.translated_paragraphs or 0),
        "failed_paragraphs": int(row.failed_paragraphs or 0),
        "percent": percent,
        "message": row.message or "",
        "job_id": row.job_id,
        "updated_at": row.updated_at,
    }


def pick_edition_needing_work(session: Session, book_key: str | None = None) -> models.BookEdition | None:
    rows = list_editions_needing_work(session, book_key=book_key, limit=1)
    return rows[0] if rows else None


def mark_paragraph_skipped(session: Session, para: models.BookParagraph) -> None:
    para.zh_text = ""
    para.zh_source = "skip"
    para.translated_at = _utc_now()
    para.updated_at = _utc_now()
    session.add(para)


def ensure_edition_from_catalog(
    session: Session,
    book_key: str,
) -> models.BookEdition | None:
    """Create shared edition+EN paragraphs from bundled Gutenberg text (no user doc required)."""
    from app.services import book_library
    from app.services.text_splitter import split_into_blocks

    key = (book_key or "").strip()
    if not key:
        return None

    existing = session.exec(
        select(models.BookEdition)
        .where(models.BookEdition.book_key == key)
        .order_by(models.BookEdition.id.desc())
    ).first()
    if existing and _existing_paragraph_count(session, existing.id) > 0:
        refresh_edition_progress(session, existing.id)
        session.commit()
        session.refresh(existing)
        return existing

    manifest = book_library._load_manifest()
    item = next((m for m in manifest if m.get("key") == key), None)
    # Build a lightweight LibraryBook-like stub for path helpers
    stub = models.LibraryBook(
        user_id=1,
        key=key,
        provider=(item or {}).get("provider") or "gutenberg",
        title=(item or {}).get("title") or key,
        author=(item or {}).get("author") or "",
        raw_url=(item or {}).get("raw_url") or "",
        repo_url=(item or {}).get("repo_url") or "",
    )
    text = book_library._read_bundled_or_cached_text(stub, item)
    if not text:
        try:
            text = book_library._download_book_text(stub) if stub.raw_url else None
        except Exception:
            text = None
    if not text:
        return existing
    text = book_library._normalize_book_text(text)
    sha = book_library._sha256_text(text)

    # Prefer filling the existing stub/edition for this book_key (avoid duplicate rows).
    if existing:
        edition = existing
        edition.content_sha256 = sha
        edition.title = stub.title or edition.title
        edition.author = stub.author or edition.author
        edition.source_url = stub.repo_url or stub.raw_url or edition.source_url
        edition.updated_at = _utc_now()
        session.add(edition)
        session.commit()
        session.refresh(edition)
    else:
        edition = get_or_create_edition(
            session,
            book_key=key,
            content_sha256=sha,
            title=stub.title,
            author=stub.author,
            source_url=stub.repo_url or stub.raw_url,
        )

    if _existing_paragraph_count(session, edition.id) == 0:
        blocks = split_into_blocks(text)
        for start in range(0, len(blocks), PARAGRAPH_INSERT_BATCH):
            batch = blocks[start : start + PARAGRAPH_INSERT_BATCH]
            rows = []
            for i, block in enumerate(batch):
                rows.append(
                    models.BookParagraph(
                        edition_id=edition.id,
                        order_index=start + i,
                        en_text=block["text"],
                        en_hash=text_hash(block["text"]),
                    )
                )
            session.add_all(rows)
            session.commit()
        edition.block_count = len(blocks)
        session.add(edition)
        session.commit()
        refresh_edition_progress(session, edition.id)
        session.commit()
        session.refresh(edition)
    return edition


def ensure_catalog_edition_stubs(session: Session, *, limit: int = 100) -> int:
    """Fast scan helper: create edition rows for catalog keys without loading full text."""
    from app.services import book_library

    created = 0
    for item in book_library._load_manifest()[: max(1, min(limit, 200))]:
        key = (item.get("key") or "").strip()
        if not key:
            continue
        existing = session.exec(
            select(models.BookEdition).where(models.BookEdition.book_key == key)
        ).first()
        if existing:
            continue
        sha = str(item.get("gutenberg_id") or item.get("asset_file") or key)
        get_or_create_edition(
            session,
            book_key=key,
            content_sha256=f"stub:{sha}",
            title=item.get("title") or key,
            author=item.get("author") or "",
            source_url=item.get("repo_url") or item.get("raw_url"),
            block_count=0,
        )
        created += 1
    return created


def ensure_catalog_editions(session: Session, *, limit: int = 100) -> int:
    """Ensure shared editions exist for curated catalog keys (stubs for fast scan)."""
    return ensure_catalog_edition_stubs(session, limit=limit)


def propagate_edition_to_user_docs(session: Session, edition_id: int, start: int, end: int) -> int:
    docs = session.exec(
        select(models.ReadingDocument).where(models.ReadingDocument.edition_id == edition_id)
    ).all()
    total = 0
    for doc in docs:
        if not doc.id:
            continue
        total += hydrate_document_range(session, doc.id, start, end, edition_id=edition_id)
    return total
