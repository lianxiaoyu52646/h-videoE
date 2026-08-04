"""Curated shelf stats must stay at catalog size (100), not raw BookEdition rows."""
from sqlmodel import Session

from app import models
from app.services import book_shared


def test_stats_ignore_non_catalog_and_dedupe(test_engine, monkeypatch):
    catalog = [{"key": f"pg_{i}"} for i in range(1, 101)]
    monkeypatch.setattr(
        "app.services.book_library._load_manifest",
        lambda: catalog,
    )

    with Session(test_engine) as session:
        for i in range(1, 101):
            session.add(
                models.BookEdition(
                    book_key=f"pg_{i}",
                    content_sha256=f"stub:{i}",
                    title=f"Book {i}",
                    translate_status="pending",
                )
            )
        # Extra: user upload outside catalog
        session.add(
            models.BookEdition(
                book_key="user_upload_xyz",
                content_sha256="sha-upload",
                title="Upload",
                translate_status="pending",
            )
        )
        # Extra: duplicate edition for same catalog key
        session.add(
            models.BookEdition(
                book_key="pg_1",
                content_sha256="real-content-hash",
                title="Book 1 real",
                block_count=10,
                translated_blocks=10,
                translate_status="done",
            )
        )
        session.commit()

        stats = book_shared.edition_translation_stats(session)
        assert stats["total_books"] == 100
        assert stats["pending_books"] == 99  # pg_1 done, rest pending
        assert stats["done_books"] == 1

        needing = book_shared.list_editions_needing_work(session, limit=200)
        assert len(needing) == 99
        assert all(r.book_key.startswith("pg_") for r in needing)
        assert "user_upload_xyz" not in {r.book_key for r in needing}
        # Prefer real content over stub for pg_1 → done → not in needing
        assert "pg_1" not in {r.book_key for r in needing}
