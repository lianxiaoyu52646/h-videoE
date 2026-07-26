"""Shared book translation write-protect + fail retry."""
from sqlmodel import Session, select

from app import models
from app.services import book_shared


def test_upsert_does_not_overwrite_existing_zh(test_engine):
    with Session(test_engine) as session:
        ed = models.BookEdition(
            book_key="pg_test_guard",
            content_sha256="abc",
            title="T",
            block_count=1,
        )
        session.add(ed)
        session.commit()
        session.refresh(ed)

        assert book_shared.upsert_paragraph_translation(
            session, ed.id, 0, "Hello", "你好", source="job"
        )
        session.commit()
        assert not book_shared.upsert_paragraph_translation(
            session, ed.id, 0, "Hello", "哈喽", source="job", force=False
        )
        session.commit()
        para = session.exec(
            select(models.BookParagraph).where(
                models.BookParagraph.edition_id == ed.id,
                models.BookParagraph.order_index == 0,
            )
        ).first()
        assert para is not None
        assert para.zh_text == "你好"

        assert book_shared.upsert_paragraph_translation(
            session, ed.id, 0, "Hello", "哈喽", source="job", force=True
        )
        session.commit()
        session.refresh(para)
        assert para.zh_text == "哈喽"


def test_mark_paragraph_failed_then_skip(test_engine):
    with Session(test_engine) as session:
        ed = models.BookEdition(
            book_key="pg_test_fail",
            content_sha256="def",
            title="F",
            block_count=1,
        )
        session.add(ed)
        session.commit()
        session.refresh(ed)
        para = models.BookParagraph(
            edition_id=ed.id,
            order_index=0,
            en_text="Something meaningful here",
            en_hash="h",
        )
        session.add(para)
        session.commit()
        session.refresh(para)

        assert book_shared.mark_paragraph_translate_failed(session, para, max_retries=3) is False
        assert para.zh_source == "error:1"
        assert book_shared.mark_paragraph_translate_failed(session, para, max_retries=3) is False
        assert para.zh_source == "error:2"
        assert book_shared.mark_paragraph_translate_failed(session, para, max_retries=3) is True
        assert para.zh_source == "skip"
        session.commit()

        missing = book_shared.list_missing_paragraphs(session, edition_id=ed.id, limit=10)
        assert missing == []
