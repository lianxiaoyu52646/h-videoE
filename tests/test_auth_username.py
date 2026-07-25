"""Username/password auth: real DB persist + password check."""
from sqlmodel import Session, select

from app import models, security


def test_register_login_and_me(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    reg = client.post("/api/auth/register", json={
        "username": "泡泡学员",
        "password": "secret12",
    })
    assert reg.status_code == 200, reg.text
    data = reg.json()
    assert data["user"]["username"] == "泡泡学员"
    assert data["user"]["display_name"] == "泡泡学员"
    assert data["token"]
    assert client.cookies.get("ve_session")

    with Session(test_engine) as session:
        row = session.exec(select(models.User).where(models.User.username == "泡泡学员")).first()
        assert row is not None
        assert row.password_hash
        assert security.verify_password("secret12", row.password_hash)
        assert not security.verify_password("wrong-pass", row.password_hash)

    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["username"] == "泡泡学员"

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    bad = client.post("/api/auth/login", json={
        "username": "泡泡学员",
        "password": "bad-password",
    })
    assert bad.status_code == 401

    login = client.post("/api/auth/login", json={
        "username": "泡泡学员",
        "password": "secret12",
    })
    assert login.status_code == 200, login.text
    assert client.get("/api/auth/me").status_code == 200


def test_register_duplicate_username(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)
    payload = {"username": "dup_user", "password": "secret12"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    again = client.post("/api/auth/register", json=payload)
    assert again.status_code == 409


def test_wechat_endpoint_removed(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    resp = client.post("/api/auth/wechat", json={"openid": "x"})
    assert resp.status_code in (404, 405)
