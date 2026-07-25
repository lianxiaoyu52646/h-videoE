"""Study feed smoke tests."""
from sqlmodel import Session, select

from app import models
from app.services import wordbook_catalog


def test_wordbook_study_feed_and_commit(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.config.settings.app_mode", "desktop")
    # install a small book
    with Session(test_engine) as session:
        from app import security
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
    payload = feed.json()
    assert len(payload["items"]) == 10
    assert payload["progress"]["total"] == 1987
    ids = [i["id"] for i in payload["items"]]
    starred = ids[:2]

    commit = client.post(
        f"/api/wordbooks/{wid}/study-commit",
        json={"entry_ids": ids, "starred_ids": starred},
    )
    assert commit.status_code == 200, commit.text
    prog = commit.json()["progress"]
    assert prog["cursor"] >= 10
    assert prog["learned"] == 8
    assert prog["unknown"] == 2

    feed2 = client.get(f"/api/wordbooks/{wid}/study-feed?limit=10")
    assert feed2.status_code == 200
    assert feed2.json()["progress"]["cursor"] >= 10
    # next batch should differ
    next_ids = [i["id"] for i in feed2.json()["items"]]
    assert next_ids[0] != ids[0]
