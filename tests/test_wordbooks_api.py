def _create_wordbook(client, name="Wordbook API Test"):
    resp = client.post("/api/wordbooks", json={
        "name": name,
        "description": "api test",
        "language": "en",
        "source_name": "test",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_wordbook_entries_api_supports_pagination_and_search(client):
    wordbook = _create_wordbook(client)
    entries = [
        {
            "word": f"term{i:02d}",
            "lemma": f"term{i:02d}",
            "translation": f"含义{i:02d}",
            "definition": f"definition {i:02d}",
            "level": "L1",
        }
        for i in range(1, 46)
    ]
    import_resp = client.post(
        f"/api/wordbooks/{wordbook['id']}/entries/import",
        json={"entries": entries},
    )
    assert import_resp.status_code == 200, import_resp.text

    page = client.get(f"/api/wordbooks/{wordbook['id']}/entries", params={
        "page": 2,
        "page_size": 20,
    }).json()
    assert page["page"] == 2
    assert page["page_size"] == 20
    assert page["total"] == 45
    assert page["total_pages"] == 3
    assert len(page["items"]) == 20

    search = client.get(f"/api/wordbooks/{wordbook['id']}/entries", params={
        "q": "term45",
    }).json()
    assert search["total"] == 1
    assert search["items"][0]["word"] == "term45"

    default_page = client.get(f"/api/wordbooks/{wordbook['id']}/entries").json()
    assert default_page["page"] == 1
    assert default_page["page_size"] == 10
    assert len(default_page["items"]) == 10

    clamped_page = client.get(f"/api/wordbooks/{wordbook['id']}/entries", params={
        "page": 99,
        "page_size": 10,
    }).json()
    assert clamped_page["page"] == clamped_page["total_pages"] == 5
    assert len(clamped_page["items"]) == 5


def test_wordbook_soft_delete_hides_from_list(client):
    wordbook = _create_wordbook(client, name="Delete Me Book")
    book_id = wordbook["id"]

    delete_resp = client.delete(f"/api/wordbooks/{book_id}")
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["ok"] is True

    listed = client.get("/api/wordbooks").json()
    assert all(item["id"] != book_id for item in listed)

    get_resp = client.get(f"/api/wordbooks/{book_id}")
    assert get_resp.status_code == 404

    recreate_resp = client.post("/api/wordbooks", json={
        "name": "Delete Me Book",
        "description": "",
        "language": "en",
        "source_name": "自定义",
    })
    assert recreate_resp.status_code == 200, recreate_resp.text


def test_wordbook_custom_list_excludes_catalog_installs(client):
    custom_before = client.get("/api/wordbooks", params={"custom": True}).json()
    custom_ids_before = {item["id"] for item in custom_before}

    install_resp = client.post("/api/wordbooks/catalog/cet4_kylebing/install")
    assert install_resp.status_code == 200, install_resp.text
    installed_id = install_resp.json()["wordbook"]["id"]

    all_books = client.get("/api/wordbooks").json()
    assert any(item["id"] == installed_id for item in all_books)

    custom_after = client.get("/api/wordbooks", params={"custom": True}).json()
    custom_ids_after = {item["id"] for item in custom_after}
    assert installed_id not in custom_ids_after
    assert custom_ids_after == custom_ids_before


def test_vocab_routes_use_fast_local_lookup(client, monkeypatch):
    def _fast(word, session=None):
        return {
            "word": word,
            "lemma": word,
            "definition": "local def",
            "pronunciation": None,
            "part_of_speech": "n.",
            "example": "local example",
            "translation": "本地释义",
            "youdao_translation": None,
            "lookup_source": "wordbook",
            "matched_word": word,
            "suggestions": [],
            "pending_enrichment": False,
        }

    def _fail(*args, **kwargs):
        raise AssertionError("online lookup should not be used")

    monkeypatch.setattr("app.routers.vocabulary.dictionary.lookup_word_fast", _fast)
    monkeypatch.setattr("app.routers.vocabulary.dictionary.lookup_word", _fail)

    lookup_resp = client.get("/api/word/localtest")
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["translation"] == "本地释义"

    save_resp = client.post("/api/vocab/save", json={
        "word": "localtest",
        "source_platform": "reading",
        "source_video_id": "reading-1",
        "source_url": "/reader?id=1",
        "source_title": "Local Only",
        "sentence": "localtest sentence",
        "sentence_translation": "本地释义句子",
    })
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json()["translation"] == "本地释义"


def test_practice_page_redirects_to_vocab(client):
    resp = client.get("/practice", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"] == "/vocab"
