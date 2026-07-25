"""PK rooms: 2-player or bot vocab battles.

Rooms are cached in memory for WebSocket fan-out, and persisted to Neon
(`PkBattleRoom`) so joins survive Render cold starts / redeploys.
"""
from __future__ import annotations

import asyncio
import logging
import random
import string
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app import crud, models
from app import database


logger = logging.getLogger(__name__)

QUESTIONS_PER_MATCH = 20
BOT_ACCURACY = 0.72
BOT_ANSWER_DELAY = (0.6, 1.8)
ROOM_TTL_HOURS = 6


@dataclass
class PlayerState:
    user_id: int
    name: str
    score: int = 0
    answers: dict[int, int] = field(default_factory=dict)  # q_index -> choice
    ready: bool = False
    is_bot: bool = False
    websocket: Any = None


@dataclass
class Room:
    code: str
    host_id: int
    mode: str  # bot | pvp
    wordbook_id: int | None = None
    status: str = "waiting"  # waiting | playing | finished
    players: dict[int, PlayerState] = field(default_factory=dict)
    questions: list[dict] = field(default_factory=list)
    current_index: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    bot_task: asyncio.Task | None = None


_rooms: dict[str, Room] = {}
_lock = asyncio.Lock()


def normalize_code(raw: str | None) -> str:
    """Normalize room codes typed on phones (spaces / full-width)."""
    text = unicodedata.normalize("NFKC", (raw or "").strip()).upper()
    return "".join(ch for ch in text if ch.isalnum())


def _gen_code() -> str:
    for _ in range(40):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in _rooms:
            return code
    raise RuntimeError("Unable to allocate room code")


def _player_to_dict(p: PlayerState) -> dict:
    return {
        "user_id": p.user_id,
        "name": p.name,
        "score": p.score,
        "answers": {str(k): v for k, v in p.answers.items()},
        "ready": p.ready,
        "is_bot": p.is_bot,
    }


def _player_from_dict(data: dict) -> PlayerState:
    answers_raw = data.get("answers") or {}
    answers = {int(k): int(v) for k, v in answers_raw.items()}
    return PlayerState(
        user_id=int(data["user_id"]),
        name=str(data.get("name") or ""),
        score=int(data.get("score") or 0),
        answers=answers,
        ready=bool(data.get("ready")),
        is_bot=bool(data.get("is_bot")),
    )


def room_to_state(room: Room) -> dict:
    return {
        "code": room.code,
        "host_id": room.host_id,
        "mode": room.mode,
        "wordbook_id": room.wordbook_id,
        "status": room.status,
        "players": {str(uid): _player_to_dict(p) for uid, p in room.players.items()},
        "questions": room.questions,
        "current_index": room.current_index,
        "started_at": room.started_at,
        "finished_at": room.finished_at,
    }


def room_from_state(data: dict, *, keep_websockets: Room | None = None) -> Room:
    room = Room(
        code=str(data["code"]).upper(),
        host_id=int(data["host_id"]),
        mode=str(data.get("mode") or "pvp"),
        wordbook_id=data.get("wordbook_id"),
        status=str(data.get("status") or "waiting"),
        questions=list(data.get("questions") or []),
        current_index=int(data.get("current_index") or 0),
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
    )
    for uid_s, pdata in (data.get("players") or {}).items():
        player = _player_from_dict(pdata)
        if keep_websockets and keep_websockets.players.get(player.user_id):
            player.websocket = keep_websockets.players[player.user_id].websocket
        room.players[int(uid_s)] = player
    return room


def _persist_room(room: Room) -> None:
    now = datetime.utcnow()
    expires = now + timedelta(hours=ROOM_TTL_HOURS)
    state = room_to_state(room)
    try:
        with Session(database.engine) as session:
            row = session.exec(
                select(models.PkBattleRoom).where(models.PkBattleRoom.code == room.code)
            ).first()
            if not row:
                row = models.PkBattleRoom(
                    code=room.code,
                    host_id=room.host_id,
                    mode=room.mode,
                    status=room.status,
                    wordbook_id=room.wordbook_id,
                    state_json=state,
                    expires_at=expires,
                    created_at=now,
                    updated_at=now,
                )
            else:
                row.host_id = room.host_id
                row.mode = room.mode
                row.status = room.status
                row.wordbook_id = room.wordbook_id
                row.state_json = state
                row.expires_at = expires
                row.updated_at = now
            session.add(row)
            session.commit()
    except Exception:
        logger.exception("persist pk room failed code=%s", room.code)


def _load_room_from_db(code: str) -> Room | None:
    code = normalize_code(code)
    if not code:
        return None
    try:
        with Session(database.engine) as session:
            row = session.exec(
                select(models.PkBattleRoom).where(models.PkBattleRoom.code == code)
            ).first()
            if not row:
                return None
            if row.expires_at and row.expires_at < datetime.utcnow():
                session.delete(row)
                session.commit()
                return None
            data = dict(row.state_json or {})
            if not data.get("code"):
                data["code"] = row.code
                data["host_id"] = row.host_id
                data["mode"] = row.mode
                data["status"] = row.status
                data["wordbook_id"] = row.wordbook_id
            return room_from_state(data)
    except Exception:
        logger.exception("load pk room failed code=%s", code)
        return None


def get_room(code: str) -> Room | None:
    code = normalize_code(code)
    if not code:
        return None
    room = _rooms.get(code)
    if room:
        return room
    room = _load_room_from_db(code)
    if room:
        _rooms[code] = room
    return room


def _cache_and_persist(room: Room) -> Room:
    _rooms[room.code] = room
    _persist_room(room)
    return room


def _pick_from_json_wordbook(session: Session, wordbook_id: int, limit: int, seen: set[str]) -> list[dict]:
    from app.services import wordbook_json_store

    cat = session.exec(
        select(models.WordBookCatalog).where(
            models.WordBookCatalog.installed_wordbook_id == wordbook_id
        )
    ).first()
    if not cat or not cat.asset_file:
        return []
    entries = list(wordbook_json_store.load_entries(cat.asset_file))
    random.shuffle(entries)
    words: list[dict] = []
    for entry in entries:
        w = (entry.get("word") or "").strip().lower()
        if not w or w in seen or " " in w:
            continue
        translation = (entry.get("translation") or entry.get("definition") or "").strip()
        if not translation:
            continue
        seen.add(w)
        words.append({"word": w, "translation": translation})
        if len(words) >= limit:
            break
    return words


def _pick_words(session: Session, user_id: int, wordbook_id: int | None, limit: int) -> list[dict]:
    words: list[dict] = []
    seen: set[str] = set()

    vocab = session.exec(
        select(models.VocabItem)
        .where(models.VocabItem.user_id == user_id)
        .order_by(models.VocabItem.due.asc())
        .limit(limit * 2)
    ).all()
    for item in vocab:
        w = (item.word or "").strip().lower()
        if not w or w in seen:
            continue
        translation = (item.translation or item.definition or "").strip()
        if not translation:
            continue
        seen.add(w)
        words.append({"word": w, "translation": translation})
        if len(words) >= limit:
            return words

    if wordbook_id:
        # Prefer curated JSON (full book); SQL entries are sparse star rows only.
        json_words = _pick_from_json_wordbook(session, wordbook_id, limit - len(words), seen)
        words.extend(json_words)
        if len(words) >= limit:
            return words[:limit]

        entries = session.exec(
            select(models.WordBookEntry)
            .where(models.WordBookEntry.wordbook_id == wordbook_id)
            .limit(limit * 4)
        ).all()
        random.shuffle(entries)
        for entry in entries:
            w = (entry.word or "").strip().lower()
            if not w or w in seen:
                continue
            translation = (entry.translation or entry.definition or "").strip()
            if not translation:
                continue
            seen.add(w)
            words.append({"word": w, "translation": translation})
            if len(words) >= limit:
                return words
    else:
        from pathlib import Path
        import sqlite3

        from app.config import settings as app_settings

        try:
            db_path = Path(app_settings.bundled_dictionary_dir) / "dictionary.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                rows = conn.execute(
                    "SELECT word, translation FROM words "
                    "WHERE translation IS NOT NULL AND trim(translation) != '' "
                    "ORDER BY RANDOM() LIMIT ?",
                    (limit * 2,),
                ).fetchall()
                conn.close()
                for w, tr in rows:
                    ww = (w or "").strip().lower()
                    if not ww or ww in seen or " " in ww:
                        continue
                    if not (tr or "").strip():
                        continue
                    seen.add(ww)
                    words.append({"word": ww, "translation": tr.strip()})
                    if len(words) >= limit:
                        return words
        except Exception:
            pass

    fallback = [
        {"word": "apple", "translation": "n. 苹果"},
        {"word": "book", "translation": "n. 书"},
        {"word": "happy", "translation": "a. 快乐的"},
        {"word": "run", "translation": "v. 跑"},
        {"word": "water", "translation": "n. 水"},
        {"word": "friend", "translation": "n. 朋友"},
        {"word": "school", "translation": "n. 学校"},
        {"word": "music", "translation": "n. 音乐"},
        {"word": "bright", "translation": "a. 明亮的"},
        {"word": "journey", "translation": "n. 旅程"},
        {"word": "curious", "translation": "a. 好奇的"},
        {"word": "gentle", "translation": "a. 温柔的"},
        {"word": "adventure", "translation": "n. 冒险"},
        {"word": "whisper", "translation": "v. 低语"},
        {"word": "courage", "translation": "n. 勇气"},
        {"word": "sparkle", "translation": "v. 闪耀"},
        {"word": "melody", "translation": "n. 旋律"},
        {"word": "garden", "translation": "n. 花园"},
        {"word": "sunrise", "translation": "n. 日出"},
        {"word": "promise", "translation": "n. 承诺"},
    ]
    for item in fallback:
        if item["word"] not in seen:
            words.append(item)
            seen.add(item["word"])
        if len(words) >= limit:
            break
    return words[:limit]


def _build_questions(pool: list[dict]) -> list[dict]:
    if len(pool) < 4:
        while len(pool) < 4:
            pool.append({"word": f"word{len(pool)}", "translation": f"释义{len(pool)}"})
    questions = []
    for i, item in enumerate(pool[:QUESTIONS_PER_MATCH]):
        distractors = [p for p in pool if p["word"] != item["word"]]
        random.shuffle(distractors)
        options = [item["word"]] + [d["word"] for d in distractors[:3]]
        while len(options) < 4:
            options.append(f"option{len(options)}")
        random.shuffle(options)
        correct = options.index(item["word"])
        questions.append(
            {
                "index": i,
                "prompt": item["translation"],
                "options": options,
                "correct": correct,
                "word": item["word"],
            }
        )
    return questions


async def create_room(
    *,
    user_id: int,
    display_name: str,
    mode: str = "bot",
    wordbook_id: int | None = None,
) -> Room:
    async with _lock:
        code = _gen_code()
        # Avoid colliding with a durable room still in DB.
        while _load_room_from_db(code) is not None:
            code = _gen_code()
        room = Room(code=code, host_id=user_id, mode=mode, wordbook_id=wordbook_id)
        room.players[user_id] = PlayerState(user_id=user_id, name=display_name or f"玩家{user_id}")
        if mode == "bot":
            bot_id = -1
            room.players[bot_id] = PlayerState(
                user_id=bot_id, name="泡泡机器人", ready=True, is_bot=True
            )
        return _cache_and_persist(room)


async def join_room(*, code: str, user_id: int, display_name: str) -> Room:
    async with _lock:
        norm = normalize_code(code)
        room = get_room(norm)
        if not room:
            raise ValueError("房间不存在或已过期，请让房主重新创建并分享新房间码")
        if room.status == "finished":
            raise ValueError("对战已结束，请创建新房间")
        if room.status == "playing" and user_id not in room.players:
            raise ValueError("对战已开始，无法加入")
        if room.mode == "bot":
            raise ValueError("机器人房不可加入，请创建「双人房」")
        if user_id in room.players:
            return _cache_and_persist(room)
        humans = [p for p in room.players.values() if not p.is_bot]
        if len(humans) >= 2:
            raise ValueError("房间已满（最多 2 人）")
        room.players[user_id] = PlayerState(user_id=user_id, name=display_name or f"玩家{user_id}")
        return _cache_and_persist(room)


def public_state(room: Room, for_user: int | None = None) -> dict:
    players = []
    for p in room.players.values():
        players.append(
            {
                "user_id": p.user_id,
                "name": p.name,
                "score": p.score,
                "ready": p.ready,
                "is_bot": p.is_bot,
                "online": bool(p.is_bot or p.websocket is not None),
                "answered": room.current_index in p.answers if room.status == "playing" else False,
            }
        )
    payload: dict[str, Any] = {
        "code": room.code,
        "mode": room.mode,
        "status": room.status,
        "players": players,
        "current_index": room.current_index,
        "total": len(room.questions) or QUESTIONS_PER_MATCH,
        "wordbook_id": room.wordbook_id,
        "host_id": room.host_id,
    }
    if room.status == "playing" and room.questions:
        q = room.questions[room.current_index]
        payload["question"] = {
            "index": q["index"],
            "prompt": q["prompt"],
            "options": q["options"],
        }
        if for_user is not None:
            player = room.players.get(for_user)
            if player and room.current_index in player.answers:
                payload["your_choice"] = player.answers[room.current_index]
                payload["correct"] = q["correct"]
    if room.status == "finished":
        payload["results"] = sorted(
            [
                {"user_id": p.user_id, "name": p.name, "score": p.score, "is_bot": p.is_bot}
                for p in room.players.values()
            ],
            key=lambda x: (-x["score"], x["name"]),
        )
        payload["missed_words"] = [
            {
                "word": q["word"],
                "translation": q["prompt"],
                "saved_to_vocab": True,
            }
            for q in _missed_questions(room, for_user)
        ]
        payload["missed_saved"] = bool(payload["missed_words"])
    return payload


def _missed_questions(room: Room, user_id: int | None) -> list[dict]:
    if user_id is None or user_id not in room.players:
        return []
    player = room.players[user_id]
    if player.is_bot:
        return []
    return [
        q
        for q in room.questions
        if player.answers.get(q["index"]) != q["correct"]
    ]


def _persist_missed_vocab(room: Room) -> None:
    humans = [p for p in room.players.values() if not p.is_bot]
    if not humans or not room.questions:
        return
    with Session(database.engine) as session:
        for player in humans:
            for q in _missed_questions(room, player.user_id):
                word = (q.get("word") or "").strip()
                if not word:
                    continue
                try:
                    crud.save_vocab_with_context(
                        session,
                        {
                            "word": word,
                            "translation": q.get("prompt") or q.get("translation") or "",
                            "definition": q.get("prompt") or "",
                            "source_platform": "pk",
                            "source_video_id": f"pk-{room.code}",
                            "source_title": "单词对战",
                            "wordbook_id": room.wordbook_id,
                        },
                        user_id=player.user_id,
                    )
                except Exception:
                    continue


async def broadcast(room: Room, event: str, extra: dict | None = None) -> None:
    dead: list[int] = []
    for pid, player in room.players.items():
        if player.is_bot or player.websocket is None:
            continue
        data = public_state(room, for_user=pid)
        if extra:
            data = {**data, **extra}
        try:
            await player.websocket.send_json({"event": event, "data": data})
        except Exception:
            dead.append(pid)
    for pid in dead:
        player = room.players.get(pid)
        if player:
            player.websocket = None
    _persist_room(room)


async def set_ready(room: Room, user_id: int, ready: bool = True) -> None:
    player = room.players.get(user_id)
    if not player:
        raise ValueError("不在房间内")
    player.ready = ready
    _persist_room(room)
    humans = [p for p in room.players.values() if not p.is_bot]
    if room.mode == "bot" and ready:
        await start_match(room)
    elif room.mode == "pvp" and len(humans) >= 2 and all(p.ready for p in humans):
        await start_match(room)
    else:
        await broadcast(room, "lobby")


async def start_match(room: Room) -> None:
    if room.status == "playing":
        return
    host = room.players.get(room.host_id) or next(iter(room.players.values()))
    with Session(database.engine) as session:
        pool = _pick_words(
            session,
            host.user_id if host.user_id > 0 else room.host_id,
            room.wordbook_id,
            QUESTIONS_PER_MATCH,
        )
    room.questions = _build_questions(pool)
    room.status = "playing"
    room.current_index = 0
    room.started_at = time.time()
    for p in room.players.values():
        p.score = 0
        p.answers = {}
    _persist_room(room)
    await broadcast(room, "question")
    if room.mode == "bot":
        room.bot_task = asyncio.create_task(_bot_loop(room))


async def submit_answer(room: Room, user_id: int, choice: int) -> None:
    if room.status != "playing":
        raise ValueError("不在对战中")
    player = room.players.get(user_id)
    if not player:
        raise ValueError("不在房间内")
    idx = room.current_index
    if idx in player.answers:
        return
    if choice < 0 or choice > 3:
        raise ValueError("无效选项")
    player.answers[idx] = choice
    q = room.questions[idx]
    if choice == q["correct"]:
        player.score += 1
    await broadcast(room, "answer")

    humans = [p for p in room.players.values() if not p.is_bot]
    bots = [p for p in room.players.values() if p.is_bot]
    needed = humans + bots
    if all(idx in p.answers for p in needed):
        await asyncio.sleep(0.45)
        await _advance(room)


async def _advance(room: Room) -> None:
    if room.current_index + 1 >= len(room.questions):
        room.status = "finished"
        room.finished_at = time.time()
        if room.bot_task and not room.bot_task.done():
            room.bot_task.cancel()
        try:
            await asyncio.to_thread(_persist_missed_vocab, room)
        except Exception:
            pass
        await broadcast(room, "finished")
        return
    room.current_index += 1
    await broadcast(room, "question")


async def _bot_loop(room: Room) -> None:
    bot = next((p for p in room.players.values() if p.is_bot), None)
    if not bot:
        return
    try:
        while room.status == "playing":
            idx = room.current_index
            if idx in bot.answers:
                await asyncio.sleep(0.2)
                continue
            delay = random.uniform(*BOT_ANSWER_DELAY)
            await asyncio.sleep(delay)
            if room.status != "playing" or room.current_index != idx:
                continue
            q = room.questions[idx]
            if random.random() < BOT_ACCURACY:
                choice = q["correct"]
            else:
                wrong = [i for i in range(4) if i != q["correct"]]
                choice = random.choice(wrong)
            await submit_answer(room, bot.user_id, choice)
    except asyncio.CancelledError:
        return


async def attach_ws(room: Room, user_id: int, websocket) -> None:
    player = room.players.get(user_id)
    if not player:
        raise ValueError("请先加入房间")
    player.websocket = websocket
    _rooms[room.code] = room
    await websocket.send_json({"event": "lobby", "data": public_state(room, for_user=user_id)})


def mark_offline(room: Room, user_id: int) -> None:
    player = room.players.get(user_id)
    if not player:
        return
    player.websocket = None
    _persist_room(room)
