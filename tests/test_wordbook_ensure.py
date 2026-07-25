"""Wordbook list recovery: login/list ensure shells for curated JSON catalogs."""
from sqlmodel import Session, select

from app import crud, models, security
from app.services import wordbook_catalog


def test_list_and_ensure_installs_catalog_shells(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", True)
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.config.settings.app_mode", "desktop")

    with Session(test_engine) as session:
        security.ensure_default_user(session)

    resp = client.get("/api/wordbooks")
    assert resp.status_code == 200, resp.text
    books = resp.json()
    assert len(books) >= 10
    assert all(b.get("entry_count", 0) > 0 for b in books[:3])

    ensured = client.post("/api/wordbooks/ensure")
    assert ensured.status_code == 200, ensured.text
    payload = ensured.json()
    assert payload["ok"] is True
    assert len(payload["books"]) >= 10


def test_install_links_existing_orphan_wordbook(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.config.settings.app_mode", "desktop")

    with Session(test_engine) as session:
        user = security.ensure_default_user(session)
        wordbook_catalog.ensure_catalog(session)
        row = session.exec(
            select(models.WordBookCatalog).where(
                models.WordBookCatalog.user_id == user.id,
                models.WordBookCatalog.key == "chuzhong_kylebing",
            )
        ).first()
        assert row is not None
        orphan = crud.create_wordbook(
            session,
            row.name,
            description="orphan",
            source_name="orphan",
            user_id=user.id,
        )
        row.installed_wordbook_id = None
        session.add(row)
        session.commit()
        orphan_id = orphan.id

    install = client.post("/api/wordbooks/catalog/chuzhong_kylebing/install")
    assert install.status_code == 200, install.text
    assert install.json()["wordbook"]["id"] == orphan_id


def test_login_auto_installs_wordbooks(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", True)

    reg = client.post(
        "/api/auth/register",
        json={"username": "wb_login_user", "password": "secret12"},
    )
    assert reg.status_code == 200, reg.text
    client.post("/api/auth/logout")

    with Session(test_engine) as session:
        user = session.exec(select(models.User).where(models.User.username == "wb_login_user")).first()
        assert user is not None
        # Simulate empty shells (e.g. previous install failed after register).
        for book in session.exec(select(models.WordBook).where(models.WordBook.user_id == user.id)).all():
            book.deleted_at = book.created_at
            book.name = f"{book.name}__deleted_{book.id}"
            session.add(book)
        for row in session.exec(
            select(models.WordBookCatalog).where(models.WordBookCatalog.user_id == user.id)
        ).all():
            row.installed_wordbook_id = None
            session.add(row)
        session.commit()

    login = client.post(
        "/api/auth/login",
        json={"username": "wb_login_user", "password": "secret12"},
    )
    assert login.status_code == 200, login.text
    books = client.get("/api/wordbooks")
    assert books.status_code == 200, books.text
    assert len(books.json()) >= 10
