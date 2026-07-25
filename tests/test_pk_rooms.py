"""PK rooms: durable join + independent race mode."""
import asyncio

from sqlmodel import Session, select

from app import models
from app.services import pk_rooms


def test_normalize_code_strips_noise():
    assert pk_rooms.normalize_code(" ab-12_c ") == "AB12C"
    assert pk_rooms.normalize_code("\uff41\uff42\uff11\uff12") == "AB12"


def test_pvp_join_survives_memory_clear(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    host = client.post("/api/auth/register", json={"username": "pk_host2", "password": "secret12"})
    assert host.status_code == 200, host.text
    created = client.post("/api/pk/rooms", json={"mode": "pvp"})
    assert created.status_code == 200, created.text
    code = created.json()["code"]
    assert created.json()["players"][0]["online"] is True

    pk_rooms._rooms.clear()

    client.post("/api/auth/logout")
    guest = client.post("/api/auth/register", json={"username": "pk_guest2", "password": "secret12"})
    assert guest.status_code == 200, guest.text

    joined = client.post("/api/pk/rooms/join", json={"code": code.lower()})
    assert joined.status_code == 200, joined.text
    body = joined.json()
    assert body["code"] == code
    assert body["status"] == "waiting"
    assert len([p for p in body["players"] if not p["is_bot"]]) == 2


def test_invite_bot_and_leave(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    client.post("/api/auth/register", json={"username": "pk_bot_inv", "password": "secret12"})
    created = client.post("/api/pk/rooms", json={"mode": "pvp"})
    code = created.json()["code"]
    invited = client.post("/api/pk/rooms/invite-bot", json={"code": code})
    assert invited.status_code == 200, invited.text
    assert any(p["is_bot"] for p in invited.json()["players"])

    left = client.post("/api/pk/rooms/leave", json={"code": code})
    assert left.status_code == 200
    assert left.json()["dissolved"] is True


def test_independent_answers_do_not_block(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    async def _run():
        room = await pk_rooms.create_room(user_id=101, display_name="A", mode="pvp")
        await pk_rooms.join_room(code=room.code, user_id=102, display_name="B")
        room = pk_rooms.get_room(room.code)
        await pk_rooms.set_ready(room, 101, True)
        room = pk_rooms.get_room(room.code)
        await pk_rooms.set_ready(room, 102, True)
        room = pk_rooms.get_room(room.code)
        assert room.status == "playing"
        assert len(room.questions) >= 4

        # A answers first question; B should still be on index 0.
        await pk_rooms.submit_answer(room, 101, room.questions[0]["correct"])
        room = pk_rooms.get_room(room.code)
        assert room.players[101].current_index == 1
        assert room.players[102].current_index == 0
        assert room.status == "playing"

    asyncio.get_event_loop().run_until_complete(_run())


def test_bot_room_rejects_join(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", False)
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)

    client.post("/api/auth/register", json={"username": "pk_bot_host3", "password": "secret12"})
    created = client.post("/api/pk/rooms", json={"mode": "bot"})
    code = created.json()["code"]
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"username": "pk_bot_guest3", "password": "secret12"})
    bad = client.post("/api/pk/rooms/join", json={"code": code})
    assert bad.status_code == 400
    assert "机器人" in bad.json()["detail"]
