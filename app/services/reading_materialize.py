"""Lazy ReadingBlock materialization for large library imports.

Free Render (~30s proxy) cannot insert thousands of Neon rows in one request.
Library imports create a document shell + chapter TOC + a small seed of blocks;
missing ranges are filled on first read from the bundled/cached txt.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from types import SimpleNamespace

from sqlmodel import Session, func, select

from app import crud, models
from app.services.reading_limits import BLOCK_INSERT_BATCH
from app.services.text_hash import text_hash
from app.services.text_splitter import split_into_blocks

logger = logging.getLogger(__name__)

# First-screen seed written during import (keeps /import under proxy timeout).
IMPORT_SEED_BLOCKS = 120
_SPLIT_CACHE_MAX = 4
_split_lock = threading.Lock()
_split_cache: "OrderedDict[str, list[dict]]" = OrderedDict()


def _cache_split(sha: str, blocks: list[dict]) -> list[dict]:
    key = (sha or "").strip()
    if not key:
        return blocks
    with _split_lock:
        _split_cache[key] = blocks
        _split_cache.move_to_end(key)
        while len(_split_cache) > _SPLIT_CACHE_MAX:
            _split_cache.popitem(last=False)
    return blocks


def _get_cached_split(sha: str) -> list[dict] | None:
    key = (sha or "").strip()
    if not key:
        return None
    with _split_lock:
        if key in _split_cache:
            _split_cache.move_to_end(key)
            return _split_cache[key]
    return None


def split_text_cached(text: str, *, content_sha: str = "") -> list[dict]:
    cached = _get_cached_split(content_sha)
    if cached is not None:
        return cached
    blocks = split_into_blocks(text)
    if content_sha:
        return _cache_split(content_sha, blocks)
    return blocks


def stored_block_count(session: Session, doc_id: int) -> int:
    return int(
        session.exec(
            select(func.count(models.ReadingBlock.id)).where(
                models.ReadingBlock.document_id == doc_id
            )
        ).one()
        or 0
    )


def is_sparse_document(session: Session, doc: models.ReadingDocument) -> bool:
    total = int(doc.block_count or 0)
    if total <= 0:
        return False
    return stored_block_count(session, doc.id) < total


def _load_source_text(session: Session, doc: models.ReadingDocument) -> tuple[str, str]:
    """Return (normalized_text, content_sha) for a library-backed document."""
    from app.services import book_library

    book_key = (doc.book_key or "").strip()
    if not book_key:
        return "", ""
    row = session.exec(
        select(models.LibraryBook).where(
            models.LibraryBook.user_id == doc.user_id,
            models.LibraryBook.key == book_key,
        )
    ).first()
    if not row:
        return "", ""
    manifest_item = next(
        (m for m in book_library._load_manifest() if m.get("key") == book_key),
        None,
    )
    text = book_library._read_bundled_or_cached_text(row, manifest_item)
    if not text:
        return "", ""
    text = book_library._normalize_book_text(text)
    sha = row.cache_sha256 or book_library._sha256_text(text)
    return text, sha


def ensure_reading_blocks_range(
    session: Session,
    doc_id: int,
    start_block: int,
    end_block: int,
) -> int:
    """Materialize missing ReadingBlocks in [start, end] from source text / shared edition."""
    doc = session.get(models.ReadingDocument, doc_id)
    if not doc or not is_sparse_document(session, doc):
        return 0

    start = max(0, int(start_block))
    end = max(start, min(int(end_block), max(int(doc.block_count or 1) - 1, 0)))
    existing = {
        int(i)
        for i in session.exec(
            select(models.ReadingBlock.order_index).where(
                models.ReadingBlock.document_id == doc_id,
                models.ReadingBlock.order_index >= start,
                models.ReadingBlock.order_index <= end,
            )
        ).all()
    }
    missing = [i for i in range(start, end + 1) if i not in existing]
    if not missing:
        return 0

    # Prefer shared edition EN when already populated (second user / prior sync).
    by_order: dict[int, tuple[str, str | None, str | None]] = {}
    if doc.edition_id:
        paras = session.exec(
            select(models.BookParagraph).where(
                models.BookParagraph.edition_id == doc.edition_id,
                models.BookParagraph.order_index >= missing[0],
                models.BookParagraph.order_index <= missing[-1],
            )
        ).all()
        for p in paras:
            by_order[int(p.order_index)] = (
                p.en_text or "",
                (p.zh_text or None),
                None,
            )

    need_from_text = [i for i in missing if i not in by_order]
    if need_from_text:
        blocks = None
        sha = ""
        if doc.edition_id:
            edition = session.get(models.BookEdition, doc.edition_id)
            if edition and edition.content_sha256:
                sha = edition.content_sha256
                blocks = _get_cached_split(sha)
        if blocks is None:
            text, sha2 = _load_source_text(session, doc)
            sha = sha or sha2
            if text:
                blocks = split_text_cached(text, content_sha=sha)
        if not blocks:
            logger.warning("sparse doc %s missing source text for materialize", doc_id)
            return 0
        for i in need_from_text:
            if 0 <= i < len(blocks):
                b = blocks[i]
                by_order[i] = (
                    b.get("text") or "",
                    (b.get("translation") or None),
                    b.get("section_title"),
                )

    created = 0
    for batch_start in range(0, len(missing), BLOCK_INSERT_BATCH):
        batch_idx = missing[batch_start : batch_start + BLOCK_INSERT_BATCH]
        rows = []
        for i in batch_idx:
            payload = by_order.get(i)
            if not payload:
                continue
            en, zh, section = payload
            rows.append(
                models.ReadingBlock(
                    document_id=doc_id,
                    order_index=i,
                    text=en,
                    translation=(zh or None),
                    section_title=section,
                    text_hash=text_hash(en),
                )
            )
        if not rows:
            continue
        session.add_all(rows)
        session.commit()
        created += len(rows)

    if created:
        try:
            from app.services import reading_cache

            reading_cache.invalidate_doc(doc_id)
        except Exception:
            pass
    return created


def create_library_reading(
    session: Session,
    title: str,
    content: str,
    *,
    source_type: str = "gutenberg-book",
    source_url: str | None = None,
    source_filename: str | None = None,
    book_key: str,
    content_sha256: str,
    author: str = "",
    user_id: int | None = None,
    seed_blocks: int = IMPORT_SEED_BLOCKS,
) -> models.ReadingDocument:
    """Create a reading shell quickly: chapters + first seed blocks only."""
    from app.services.reading_chapters import derive_chapter_specs
    from app.services import book_shared

    uid = user_id if user_id is not None else crud._required_user_id(None)
    blocks_text = split_text_cached(content, content_sha=content_sha256)
    word_count = len(content.split())
    seed_n = max(1, min(int(seed_blocks), len(blocks_text) or 1))

    doc = models.ReadingDocument(
        user_id=uid,
        title=(title or "").strip() or "Untitled",
        block_count=len(blocks_text),
        word_count=word_count,
        translate_status="ready",
        translate_progress=0,
        translated_blocks=0,
        status_message=f"书库书籍已打开（{len(blocks_text)} 段，按需加载）",
        source_type=source_type,
        source_url=source_url,
        source_filename=source_filename,
        book_key=book_key,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    # Seed first screen only.
    for batch_start in range(0, seed_n, BLOCK_INSERT_BATCH):
        batch = blocks_text[batch_start : min(seed_n, batch_start + BLOCK_INSERT_BATCH)]
        items = [
            models.ReadingBlock(
                document_id=doc.id,
                order_index=batch_start + i,
                text=block["text"],
                translation=(block.get("translation") or None),
                section_title=block.get("section_title"),
                text_hash=text_hash(block["text"]),
            )
            for i, block in enumerate(batch)
        ]
        session.add_all(items)
        session.commit()

    # Chapter TOC from full in-memory split (no need for all ReadingBlocks).
    metas = [
        SimpleNamespace(order_index=i, section_title=b.get("section_title"))
        for i, b in enumerate(blocks_text)
    ]
    specs = derive_chapter_specs(metas)
    for index, spec in enumerate(specs):
        session.add(
            models.ReadingChapter(
                document_id=doc.id,
                chapter_index=index,
                title=spec["title"],
                start_block=spec["start_block"],
                end_block=spec["end_block"],
                block_count=spec["block_count"],
            )
        )
    session.commit()

    try:
        book_shared.attach_edition_to_document(
            session,
            doc,
            book_key=book_key,
            content_sha256=content_sha256,
            author=author,
            sync_paragraphs=True,  # only seeds existing ReadingBlocks
            hydrate_blocks=80,
        )
        session.refresh(doc)
    except Exception:
        logger.exception("attach edition failed for library book %s", book_key)

    return doc
