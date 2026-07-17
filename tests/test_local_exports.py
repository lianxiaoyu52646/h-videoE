import io
import json
import zipfile


def test_export_vocab_json(client):
    save_resp = client.post("/api/vocab/save", json={
        "word": "wizard",
        "source_platform": "reading",
        "source_video_id": "reading-1",
        "source_url": "/reader?id=1",
        "source_title": "Wizard Story",
        "sentence": "A young wizard opened the book.",
        "sentence_translation": "一个年轻的巫师打开了书。",
    })
    assert save_resp.status_code == 200, save_resp.text

    resp = client.get("/api/app/export/vocab")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    payload = json.loads(resp.text)
    assert any(item["word"] == "wizard" for item in payload)


def test_export_backup_zip(client):
    book_resp = client.post("/api/wordbooks", json={
        "name": "Backup Test Book",
        "description": "for backup export",
        "language": "en",
        "source_name": "test",
    })
    assert book_resp.status_code == 200, book_resp.text
    book = book_resp.json()

    import_resp = client.post(f"/api/wordbooks/{book['id']}/entries/import", json={
        "entries": [
            {
                "word": "coherent",
                "lemma": "coherent",
                "definition": "logical and consistent",
                "translation": "连贯的",
                "tags": ["backup"],
            }
        ]
    })
    assert import_resp.status_code == 200, import_resp.text

    resp = client.get("/api/app/backup")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        assert "videoenglish.sqlite3" in names
        assert "vocab.json" in names
        assert "wordbooks.json" in names
        assert "meta.json" in names

        meta = json.loads(zf.read("meta.json").decode("utf-8"))
        assert meta["wordbook_count"] >= 1
