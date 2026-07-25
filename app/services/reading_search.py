"""阅读段落搜索 — FTS5 加速大书检索"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
from typing import Iterable

from sqlmodel import Session, func, select

from app import database, models

logger = logging.getLogger(__name__)

_FTS_READY = False
_index_lock = threading.Lock()
_indexing_docs: set[int] = set()


def _conn():
    raw = database.engine.raw_connection()
    return raw


def ensure_fts_schema() -> None:
    global _FTS_READY
    if _FTS_READY:
        return
    from app.config import settings

    if not settings.is_sqlite:
        _FTS_READY = True
        return
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS readingblock_fts USING fts5(
                document_id UNINDEXED,
                order_index UNINDEXED,
                block_id UNINDEXED,
                body,
                tokenize='unicode61 remove_diacritics 0'
            )
            """
        )
        conn.commit()
        _FTS_READY = True
    finally:
        conn.close()


def _escape_fts_query(query: str) -> str:
    cleaned = re.sub(r'["\'\\]+', " ", (query or "").strip())
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return ""
    return " ".join(f'"{p}"*' for p in parts[:8])


def fts_indexed_count(doc_id: int) -> int:
    ensure_fts_schema()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM readingblock_fts WHERE document_id = ?",
            (doc_id,),
        )
        row = cur.fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def delete_document_index(doc_id: int) -> None:
    ensure_fts_schema()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM readingblock_fts WHERE document_id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def index_blocks_batch(
    doc_id: int,
    blocks: Iterable[tuple[int, int, str]],
) -> int:
    """增量写入 FTS（block_id, order_index, text）。"""
    ensure_fts_schema()
    rows = [(doc_id, order_index, block_id, text or "") for block_id, order_index, text in blocks]
    if not rows:
        return 0
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO readingblock_fts(document_id, order_index, block_id, body) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def index_document(session: Session, doc_id: int) -> int:
    from app.config import settings

    if not settings.is_sqlite:
        return 0
    ensure_fts_schema()
    blocks = session.exec(
        select(models.ReadingBlock.id, models.ReadingBlock.order_index, models.ReadingBlock.text).where(
            models.ReadingBlock.document_id == doc_id
        )
    ).all()
    if not blocks:
        return 0
    delete_document_index(doc_id)
    return index_blocks_batch(
        doc_id,
        ((int(b[0]), int(b[1]), b[2] or "") for b in blocks),
    )


def ensure_document_indexed(session: Session, doc_id: int) -> None:
    """大书延迟索引：首次搜索时后台补建 FTS。"""
    doc = session.get(models.ReadingDocument, doc_id)
    if not doc or not doc.block_count:
        return
    indexed = fts_indexed_count(doc_id)
    if indexed >= doc.block_count * 0.95:
        return
    with _index_lock:
        if doc_id in _indexing_docs:
            return
        _indexing_docs.add(doc_id)

    def _run() -> None:
        try:
            from sqlmodel import Session as DbSession

            with DbSession(database.engine) as db:
                index_document(db, doc_id)
        except Exception:
            logger.exception("background FTS index failed doc=%s", doc_id)
        finally:
            _indexing_docs.discard(doc_id)

    threading.Thread(target=_run, daemon=True, name=f"fts-index-{doc_id}").start()


def search_blocks(session: Session, doc_id: int, query: str, limit: int = 50) -> list[dict]:
    needle = (query or "").strip()
    if len(needle) < 2:
        return []

    ensure_fts_schema()
    ensure_document_indexed(session, doc_id)
    fts_q = _escape_fts_query(needle)
    hits: list[tuple[int, int, int]] = []

    if fts_q and fts_indexed_count(doc_id) > 0:
        conn = _conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT block_id, order_index, bm25(readingblock_fts) AS rank
                FROM readingblock_fts
                WHERE document_id = ? AND body MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (doc_id, fts_q, limit),
            )
            hits = [(row[0], row[1], row[2]) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            hits = []
        finally:
            conn.close()

    if hits:
        block_ids = [h[0] for h in hits]
        blocks = session.exec(
            select(models.ReadingBlock).where(models.ReadingBlock.id.in_(block_ids))
        ).all()
        block_map = {b.id: b for b in blocks}
        results = []
        needle_lower = needle.lower()
        for block_id, order_index, _rank in hits:
            block = block_map.get(block_id)
            if not block:
                continue
            position = block.text.lower().find(needle_lower)
            if position < 0:
                position = 0
            start = max(0, position - 50)
            end = min(len(block.text), position + len(needle) + 50)
            snippet = block.text[start:end]
            if start > 0:
                snippet = "…" + snippet
            if end < len(block.text):
                snippet = snippet + "…"
            results.append(
                {
                    "block_id": block.id,
                    "order_index": block.order_index,
                    "section_title": block.section_title,
                    "snippet": snippet,
                    "match_start": position,
                    "match_end": position + len(needle),
                }
            )
        return results

    pattern = f"%{needle.lower()}%"
    blocks = session.exec(
        select(models.ReadingBlock)
        .where(
            models.ReadingBlock.document_id == doc_id,
            func.lower(models.ReadingBlock.text).like(pattern),
        )
        .order_by(models.ReadingBlock.order_index.asc())
        .limit(limit)
    ).all()
    results = []
    needle_lower = needle.lower()
    for block in blocks:
        position = block.text.lower().find(needle_lower)
        start = max(0, position - 50)
        end = min(len(block.text), position + len(needle) + 50)
        snippet = block.text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(block.text):
            snippet = snippet + "…"
        results.append(
            {
                "block_id": block.id,
                "order_index": block.order_index,
                "section_title": block.section_title,
                "snippet": snippet,
                "match_start": position,
                "match_end": position + len(needle),
            }
        )
    return results
