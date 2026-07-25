"""PK missed words auto-save into vocab notebook."""
from app.services import pk_rooms
from app.services.pk_rooms import PlayerState, Room


def test_persist_missed_vocab(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.app_mode", "web")
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.services.pk_rooms.database.engine", test_engine)

    from app import security
    from sqlmodel import Session, select
    from app import models

    with Session(test_engine) as session:
        user = security.ensure_default_user(session)
        uid = user.id

    room = Room(code="TEST01", host_id=uid, mode="bot")
    room.players[uid] = PlayerState(user_id=uid, name="me")
    room.players[-1] = PlayerState(user_id=-1, name="bot", is_bot=True)
    room.questions = [
        {"index": 0, "word": "apple", "prompt": "苹果", "correct": 0, "options": ["apple", "a", "b", "c"]},
        {"index": 1, "word": "banana", "prompt": "香蕉", "correct": 1, "options": ["x", "banana", "y", "z"]},
        {"index": 2, "word": "cat", "prompt": "猫", "correct": 2, "options": ["a", "b", "cat", "d"]},
    ]
    # wrong / unanswered / correct
    room.players[uid].answers = {0: 3, 2: 2}

    pk_rooms._persist_missed_vocab(room)

    with Session(test_engine) as session:
        words = {
            c.word
            for c in session.exec(
                select(models.VocabItem).where(models.VocabItem.user_id == uid)
            ).all()
        }
    assert "apple" in words
    assert "banana" in words
    assert "cat" not in words
