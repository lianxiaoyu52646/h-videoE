"""Resume cursor + absolute offset browsing for wordbook study."""
from sqlmodel import Session, select

from app import models, security
from app.services import wordbook_catalog


def test_study_feed_offset_and_cursor_resume(client, test_engine, monkeypatch):
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

    page = client.get(f"/api/wordbooks/{wid}/study-feed?limit=5&offset=20")
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["offset"] == 20
    assert body["has_more_before"] is True
    assert body["has_more_after"] is True
    assert len(body["items"]) == 5
    assert body["items"][0]["offset"] == 20

    saved = client.post(f"/api/wordbooks/{wid}/study-cursor", json={"cursor": 20})
    assert saved.status_code == 200, saved.text
    assert saved.json()["progress"]["cursor"] == 20

    resume = client.get(f"/api/wordbooks/{wid}/study-feed?limit=5")
    assert resume.status_code == 200
    resumed = resume.json()
    assert resumed["offset"] == 20
    assert resumed["items"][0]["id"] == body["items"][0]["id"]

    earlier = client.get(f"/api/wordbooks/{wid}/study-feed?limit=5&offset=15")
    assert earlier.status_code == 200
    early = earlier.json()
    assert early["offset"] == 15
    assert early["items"][-1]["offset"] == 19
    assert early["has_more_before"] is True
