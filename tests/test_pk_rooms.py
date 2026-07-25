"""PK rooms: durable join across process memory loss (Render restart)."""
from sqlmodel import Session, select

from app import models, security
from app.services import pk_rooms


def test_normalize_code_strips_noise():
    assert pk_rooms.normalize_code(" ab-12_c ") == "AB12C"
    assert pk_rooms.normalize_code("\uff41\uff42\uff11\uff12") == "AB12"


def test_pvp_join_survives_memory_clear(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    host = client.post("/api/auth/register", json={"username": "pk_host", "password": "secret12"})
    assert host.status_code == 200, host.text
    created = client.post("/api/pk/rooms", json={"mode": "pvp"})
    assert created.status_code == 200, created.text
    code = created.json()["code"]
    assert len(code) == 6

    # Simulate Render restart: wipe in-memory cache, keep Neon/SQLite row.
    pk_rooms._rooms.clear()

    client.post("/api/auth/logout")
    guest = client.post("/api/auth/register", json={"username": "pk_guest", "password": "secret12"})
    assert guest.status_code == 200, guest.text

    joined = client.post("/api/pk/rooms/join", json={"code": code.lower()})
    assert joined.status_code == 200, joined.text
    body = joined.json()
    assert body["code"] == code
    assert body["status"] == "waiting"
    assert len([p for p in body["players"] if not p["is_bot"]]) == 2

    with Session(test_engine) as session:
        row = session.exec(select(models.PkBattleRoom).where(models.PkBattleRoom.code == code)).first()
        assert row is not None
        assert row.status == "waiting"


def test_bot_room_rejects_join(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    client.post("/api/auth/register", json={"username": "pk_bot_host", "password": "secret12"})
    created = client.post("/api/pk/rooms", json={"mode": "bot"})
    code = created.json()["code"]
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "pk_bot_guest", "password": "secret12"})
    bad = client.post("/api/pk/rooms/join", json={"code": code})
    assert bad.status_code == 400
    assert "机器人" in bad.json()["detail"]
