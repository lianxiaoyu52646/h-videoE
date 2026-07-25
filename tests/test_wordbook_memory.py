"""Wordbook memory table persists per-user progress."""
from sqlmodel import Session, select

from app import models, security
from app.services import wordbook_catalog


def test_wordbook_memory_persists(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.config.settings.app_mode", "desktop")

    with Session(test_engine) as session:
        security.ensure_default_user(session)
        token = security.set_current_user(1)
        try:
            wordbook_catalog.install_catalog_wordbook(session, "chuzhong_kylebing", user_id=1)
            row = session.exec(
                select(models.WordBookCatalog).where(models.WordBookCatalog.key == "chuzhong_kylebing")
            ).first()
            wid = row.installed_wordbook_id
        finally:
            security.reset_current_user(token)

    feed = client.get(f"/api/wordbooks/{wid}/study-feed?limit=10")
    assert feed.status_code == 200, feed.text
    ids = [i["id"] for i in feed.json()["items"]]
    starred = ids[:2]

    commit = client.post(
        f"/api/wordbooks/{wid}/study-commit",
        json={"entry_ids": ids, "starred_ids": starred},
    )
    assert commit.status_code == 200, commit.text

    with Session(test_engine) as session:
        mem = session.exec(
            select(models.WordBookMemory).where(
                models.WordBookMemory.user_id == 1,
                models.WordBookMemory.wordbook_id == wid,
            )
        ).first()
        assert mem is not None
        assert mem.cursor_offset >= 10
        assert mem.known_count == 8
        assert mem.unknown_count == 2
        assert mem.last_studied_at is not None

        words = session.exec(
            select(models.WordBookMemoryWord).where(
                models.WordBookMemoryWord.user_id == 1,
                models.WordBookMemoryWord.wordbook_id == wid,
            )
        ).all()
        assert len(words) == 10
        unknown = [w for w in words if w.status == "unknown"]
        known = [w for w in words if w.status == "known"]
        assert len(unknown) == 2
        assert len(known) == 8

    # Resume from persisted cursor
    feed2 = client.get(f"/api/wordbooks/{wid}/study-feed?limit=10")
    assert feed2.status_code == 200
    assert feed2.json()["progress"]["cursor"] >= 10
    assert feed2.json()["items"][0]["id"] != ids[0]
