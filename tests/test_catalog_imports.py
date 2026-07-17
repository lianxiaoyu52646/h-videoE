from pathlib import Path

from sqlmodel import Session, select

from app import models
from app.services import book_library


def test_wordbook_catalog_install_persists_entries(client, test_engine):
    resp = client.get("/api/wordbooks/catalog")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    keys = {item["key"] for item in items}
    assert {"cet4_kylebing", "cet6_kylebing", "toefl_gungorkaya", "ielts_grokwords"} <= keys

    install_resp = client.post("/api/wordbooks/catalog/toefl_gungorkaya/install")
    assert install_resp.status_code == 200, install_resp.text
    payload = install_resp.json()
    assert payload["ok"] is True
    assert payload["catalog"]["key"] == "toefl_gungorkaya"
    assert payload["wordbook"]["name"] == "TOEFL Essential 1000"
    assert payload["imported_count"] == 1000

    with Session(test_engine) as session:
        catalog = session.exec(
            select(models.WordBookCatalog).where(models.WordBookCatalog.key == "toefl_gungorkaya")
        ).first()
        assert catalog is not None
        assert catalog.installed_wordbook_id is not None
        entries = session.exec(
            select(models.WordBookEntry).where(models.WordBookEntry.wordbook_id == catalog.installed_wordbook_id)
        ).all()
        assert len(entries) == 1000


def test_library_book_import_caches_and_links_reading(client, test_engine, tmp_path, monkeypatch):
    cache_dir = tmp_path / "book-cache"
    monkeypatch.setattr("app.config.settings.app_book_cache_dir", cache_dir)

    sample_text = """
*** START OF THE PROJECT GUTENBERG EBOOK SAMPLE ***
Chapter 1

It is a truth universally acknowledged that a single man in possession of a good fortune must be in want of a wife.

Chapter 2

Mr. Bennet was among the earliest of those who waited on Mr. Bingley.
*** END OF THE PROJECT GUTENBERG EBOOK SAMPLE ***
""".strip()

    monkeypatch.setattr(book_library, "_download_book_text", lambda row: sample_text)

    resp = client.get("/api/readings/library/books")
    assert resp.status_code == 200, resp.text
    books = resp.json()
    assert any(item["key"] == "pride_prejudice_1342" for item in books)

    import_resp = client.post("/api/readings/library/books/pride_prejudice_1342/import")
    assert import_resp.status_code == 200, import_resp.text
    payload = import_resp.json()
    assert payload["ok"] is True
    assert payload["created"] is True
    reading_id = payload["reading"]["id"]

    with Session(test_engine) as session:
        book = session.exec(
            select(models.LibraryBook).where(models.LibraryBook.key == "pride_prejudice_1342")
        ).first()
        assert book is not None
        assert book.cache_status == "cached"
        assert book.reading_document_id == reading_id
        assert book.cache_path
        cache_path = Path(book.cache_path)
        assert cache_path.exists()
        cached_text = cache_path.read_text(encoding="utf-8")
        assert "START OF THE PROJECT GUTENBERG" not in cached_text
        assert "truth universally acknowledged" in cached_text

    second_resp = client.post("/api/readings/library/books/pride_prejudice_1342/import")
    assert second_resp.status_code == 200, second_resp.text
    second_payload = second_resp.json()
    assert second_payload["created"] is False
    assert second_payload["reading"]["id"] == reading_id

    delete_resp = client.delete(f"/api/readings/{reading_id}?delete_vocab=false")
    assert delete_resp.status_code == 200, delete_resp.text

    with Session(test_engine) as session:
        book = session.exec(
            select(models.LibraryBook).where(models.LibraryBook.key == "pride_prejudice_1342")
        ).first()
        assert book is not None
        assert book.reading_document_id is None


def test_local_readings_exclude_linked_library_books(client, test_engine, tmp_path, monkeypatch):
    cache_dir = tmp_path / "book-cache"
    monkeypatch.setattr("app.config.settings.app_book_cache_dir", cache_dir)
    monkeypatch.setattr(book_library, "_download_book_text", lambda row: "Local list should hide linked GitHub books.")

    local_before = client.get("/api/readings", params={"local": True}).json()
    local_ids_before = {item["id"] for item in local_before}

    import_resp = client.post("/api/readings/library/books/pride_prejudice_1342/import")
    assert import_resp.status_code == 200, import_resp.text
    reading_id = import_resp.json()["reading"]["id"]

    all_items = client.get("/api/readings").json()
    assert any(item["id"] == reading_id for item in all_items)

    local_after = client.get("/api/readings", params={"local": True}).json()
    local_ids_after = {item["id"] for item in local_after}
    assert reading_id not in local_ids_after
    assert local_ids_after == local_ids_before


def test_local_reading_soft_delete_hides_from_list(client):
    create_resp = client.post("/api/readings", json={
        "title": "Soft Delete Reading",
        "content": "Hello world for soft delete test.",
    })
    assert create_resp.status_code == 200, create_resp.text
    doc_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/readings/{doc_id}", params={"delete_vocab": False})
    assert delete_resp.status_code == 200, delete_resp.text

    assert client.get(f"/api/readings/{doc_id}").status_code == 404
    local_items = client.get("/api/readings", params={"local": True}).json()
    assert all(item["id"] != doc_id for item in local_items)
