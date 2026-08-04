"""Claim/submit APIs for on-device novel translation persist+share."""
from sqlmodel import Session, select

from app import models
from app.routers import jobs as jobs_router
from app.services import book_shared
from app import schemas


def test_claim_and_submit_persist(test_engine, monkeypatch):
    catalog = [{"key": "pg_11", "title": "Alice", "gutenberg_id": 11}]
    monkeypatch.setattr("app.services.book_library._load_manifest", lambda: catalog)

    with Session(test_engine) as session:
        ed = models.BookEdition(
            book_key="pg_11",
            content_sha256="sha-alice",
            title="Alice",
            block_count=2,
            translated_blocks=0,
            translate_status="pending",
        )
        session.add(ed)
        session.commit()
        session.refresh(ed)

        session.add_all(
            [
                models.BookParagraph(
                    edition_id=ed.id, order_index=0, en_text="Alice was beginning to get very tired.", en_hash="a"
                ),
                models.BookParagraph(
                    edition_id=ed.id, order_index=1, en_text="So she was considering in her own mind.", en_hash="b"
                ),
            ]
        )
        session.commit()

        # Avoid trying to load bundled gutenberg text in claim.
        monkeypatch.setattr(
            book_shared,
            "_existing_paragraph_count",
            lambda sess, eid: 2,
        )
        monkeypatch.setattr(
            book_shared,
            "ensure_catalog_editions",
            lambda sess, limit=100: 0,
        )

        claimed = jobs_router._claim_next_batch(
            session, limit=5, ensure_catalog=False, book_key=None
        )
        assert claimed.ok
        assert not claimed.done
        assert len(claimed.items) == 2

        body = schemas.BookTranslateSubmitRequest(
            items=[
                schemas.BookTranslateSubmitItem(
                    edition_id=ed.id,
                    order_index=0,
                    en_text=claimed.items[0].en_text,
                    zh_text="爱丽丝开始觉得非常疲倦。",
                )
            ],
            source="qwen_local",
        )
        # Inline submit logic (endpoint uses Depends)
        saved = 0
        for item in body.items:
            if book_shared.upsert_paragraph_translation(
                session,
                item.edition_id,
                item.order_index,
                item.en_text,
                item.zh_text,
                source=body.source,
            ):
                saved += 1
        book_shared.refresh_edition_progress(session, ed.id)
        session.commit()
        session.refresh(ed)

        assert saved == 1
        assert ed.translated_blocks == 1
        assert ed.translate_status == "partial"

        para = session.exec(
            select(models.BookParagraph).where(
                models.BookParagraph.edition_id == ed.id,
                models.BookParagraph.order_index == 0,
            )
        ).first()
        assert para.zh_text.startswith("爱丽丝")
        assert para.zh_source == "qwen_local"
