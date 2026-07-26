"""Library import must stay under proxy timeout: seed blocks + lazy materialize."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app import models, security
from app.services.book_library import _normalize_book_text, _sha256_text
from app.services.reading_materialize import (
    IMPORT_SEED_BLOCKS,
    create_library_reading,
    ensure_reading_blocks_range,
    stored_block_count,
)


def test_create_library_reading_seeds_then_materializes(test_engine):
    raw = Path("app/assets/books/gutenberg/46.txt").read_text(encoding="utf-8", errors="replace")
    text = _normalize_book_text(raw)
    sha = _sha256_text(text)

    with Session(test_engine) as session:
        user = security.ensure_default_user(session)
        token = security.set_current_user(user.id)
        try:
            doc = create_library_reading(
                session,
                "A Christmas Carol",
                text,
                book_key="pg_46",
                content_sha256=sha,
                author="Dickens",
                user_id=user.id,
                seed_blocks=IMPORT_SEED_BLOCKS,
            )
            assert doc.id
            assert doc.block_count > IMPORT_SEED_BLOCKS
            assert stored_block_count(session, doc.id) == IMPORT_SEED_BLOCKS
            assert doc.edition_id

            chapters = session.exec(
                select(models.ReadingChapter)
                .where(models.ReadingChapter.document_id == doc.id)
                .order_by(models.ReadingChapter.chapter_index)
            ).all()
            assert chapters
            assert chapters[0].start_block == 0

            start = min(500, doc.block_count - 10)
            end = start + 9
            created = ensure_reading_blocks_range(session, doc.id, start, end)
            assert created == 10
            blocks = session.exec(
                select(models.ReadingBlock)
                .where(
                    models.ReadingBlock.document_id == doc.id,
                    models.ReadingBlock.order_index >= start,
                    models.ReadingBlock.order_index <= end,
                )
                .order_by(models.ReadingBlock.order_index)
            ).all()
            assert len(blocks) == 10
            assert all((b.text or "").strip() for b in blocks)
        finally:
            security.reset_current_user(token)
