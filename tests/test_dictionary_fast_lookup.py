from app.services import dictionary


def test_app_shell_reports_desktop_mode(client):
    resp = client.get("/api/app-shell")
    assert resp.status_code == 200
    data = resp.json()
    assert data["desktop_mode"] is True
    assert data["supports_login"] is False
    assert data["supports_extension"] is False


def test_fast_lookup_hits_local_core_pack(client):
    resp = client.get("/api/word-fast/wizard")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "wizard"
    assert data["translation"] == "巫师"
    assert data["lookup_source"] == "core_en"
    assert data["pending_enrichment"] is False


def test_fast_lookup_hits_ecdict_sqlite(client):
    # serendipity 不在精简 JSON 词包里，应命中完整 ECDICT SQLite。
    resp = client.get("/api/word-fast/serendipity")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "serendipity"
    assert data["lookup_source"] == "ecdict"
    assert data["translation"]
    assert "偶然" in data["translation"] or "运气" in data["translation"]


def test_fast_lookup_lemmatizes_plural(client):
    resp = client.get("/api/word-fast/wizards")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "wizard"
    assert data["matched_word"] == "wizard"
    assert data["translation"] == "巫师"


def test_fast_lookup_supports_explicit_irregular_forms(client):
    resp = client.get("/api/word-fast/analyses")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "analysis"
    assert data["matched_word"] == "analyses"
    assert data["translation"] == "分析"
    assert data["lookup_source"] == "essentials_en"
    assert data["pending_enrichment"] is False


def test_fast_lookup_returns_fuzzy_local_suggestions(client):
    resp = client.get("/api/word-fast/wizrad")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "wizrad"
    assert "wizard" in data["suggestions"]


def test_wordbook_entries_join_fast_lookup(client):
    book_resp = client.post("/api/wordbooks", json={
        "name": "IELTS Local Pack",
        "description": "local fast lookup source",
        "language": "en",
        "source_name": "IELTS",
    })
    assert book_resp.status_code == 200, book_resp.text
    book = book_resp.json()

    import_resp = client.post(f"/api/wordbooks/{book['id']}/entries/import", json={
        "entries": [
            {
                "word": "coherent",
                "lemma": "coherent",
                "translation": "条理清晰的",
                "tags": ["ielts"],
                "level": "IELTS",
            }
        ]
    })
    assert import_resp.status_code == 200, import_resp.text

    # 清掉在线缓存影响，确保命中本地词书来源。
    dictionary._ENGINE.invalidate()

    resp = client.get("/api/word-fast/coherent")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["word"] == "coherent"
    assert data["translation"] == "条理清晰的"
    assert data["definition"] == "Logical, clear, and easy to follow."
    assert data["lookup_source"] == "wordbook"
