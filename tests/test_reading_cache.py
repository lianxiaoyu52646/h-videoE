"""阅读缓存与 bootstrap API 测试"""
import pytest


@pytest.fixture(autouse=True)
def _no_bg(monkeypatch):
    monkeypatch.setattr("app.routers.readings._start_translate", lambda doc_id: None)


def test_bootstrap_returns_first_page(client, wizard_story_text):
    r = client.post("/api/readings", json={
        "title": "Bootstrap test",
        "content": wizard_story_text,
        "source_type": "paste",
    })
    doc_id = r.json()["id"]
    boot = client.get(f"/api/readings/{doc_id}/bootstrap?limit=5").json()
    assert boot["doc"]["id"] == doc_id
    assert len(boot["blocks"]) <= 5
    assert boot["blocks_total"] == boot["doc"]["block_count"]
    assert "highlights" in boot and "vocab_stats" in boot


def test_blocks_pagination(client, wizard_story_text):
    r = client.post("/api/readings", json={
        "title": "Page test",
        "content": wizard_story_text,
        "source_type": "paste",
    })
    doc_id = r.json()["id"]
    page = client.get(f"/api/readings/{doc_id}/blocks?offset=0&limit=3").json()
    assert "items" in page
    assert len(page["items"]) == 3
    assert page["total"] >= 3
    assert page["has_more"] is True

    full = client.get(f"/api/readings/{doc_id}/blocks").json()
    assert isinstance(full, list)
    assert len(full) == page["total"]


def test_translation_cache(client, wizard_story_text):
    from app import crud
    from app.database import engine
    from sqlmodel import Session

    with Session(engine) as session:
        crud.save_translation_cache(session, "Hello unique cache test.", "你好缓存测试。")
        session.commit()
        assert crud.get_translation_from_cache(session, "Hello unique cache test.") == "你好缓存测试。"
