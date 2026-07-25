"""Wordbook study feed + per-user durable memory (DB persisted)."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, func, select

from app import crud, models, security
from app.services import dictionary
from app.services import wordbook_json_store

# Study-feed item ids for JSON-backed books: VIRTUAL_ID_BASE + offset
VIRTUAL_ID_BASE = 50_000_000


def _user_id() -> int:
    return security.get_current_user_id(required=True)


def _catalog_for_wordbook(session: Session, wordbook_id: int) -> models.WordBookCatalog | None:
    return session.exec(
        select(models.WordBookCatalog).where(
            models.WordBookCatalog.installed_wordbook_id == wordbook_id
        )
    ).first()


def _json_asset_for_wordbook(session: Session, wordbook_id: int) -> str | None:
    row = _catalog_for_wordbook(session, wordbook_id)
    if row and row.asset_file and wordbook_json_store.asset_path(row.asset_file).exists():
        return row.asset_file
    return None


def _sql_entry_count(session: Session, wordbook_id: int) -> int:
    return int(
        session.exec(
            select(func.count(models.WordBookEntry.id)).where(
                models.WordBookEntry.wordbook_id == wordbook_id
            )
        ).one()
        or 0
    )


def _total_entries(session: Session, wordbook_id: int) -> int:
    asset = _json_asset_for_wordbook(session, wordbook_id)
    if asset:
        return len(wordbook_json_store.load_entries(asset))
    cat = _catalog_for_wordbook(session, wordbook_id)
    if cat and cat.entry_count:
        return int(cat.entry_count)
    return _sql_entry_count(session, wordbook_id)


def _ensure_sparse_entry(
    session: Session,
    wordbook_id: int,
    *,
    word: str,
    translation: str = "",
    pronunciation: str = "",
    definition: str = "",
) -> models.WordBookEntry:
    """Create/find a single WordBookEntry for starring (not full-book import)."""
    existing = session.exec(
        select(models.WordBookEntry).where(
            models.WordBookEntry.wordbook_id == wordbook_id,
            models.WordBookEntry.word == word,
        )
    ).first()
    if existing:
        return existing
    entry = models.WordBookEntry(
        wordbook_id=wordbook_id,
        word=word,
        translation=translation or None,
        pronunciation=pronunciation or None,
        definition=definition or "",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_or_create_memory(
    session: Session,
    wordbook_id: int,
    *,
    user_id: int | None = None,
) -> models.WordBookMemory:
    uid = user_id if user_id is not None else _user_id()
    row = session.exec(
        select(models.WordBookMemory).where(
            models.WordBookMemory.user_id == uid,
            models.WordBookMemory.wordbook_id == wordbook_id,
        )
    ).first()
    if row:
        return row
    total = _total_entries(session, wordbook_id)
    row = models.WordBookMemory(
        user_id=uid,
        wordbook_id=wordbook_id,
        total_count=total,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# Alias used by older call sites / tests
get_or_create_progress = get_or_create_memory


def _recount_memory(session: Session, memory: models.WordBookMemory) -> None:
    known = int(
        session.exec(
            select(func.count(models.WordBookMemoryWord.id)).where(
                models.WordBookMemoryWord.user_id == memory.user_id,
                models.WordBookMemoryWord.wordbook_id == memory.wordbook_id,
                models.WordBookMemoryWord.status == "known",
            )
        ).one()
        or 0
    )
    unknown = int(
        session.exec(
            select(func.count(models.WordBookMemoryWord.id)).where(
                models.WordBookMemoryWord.user_id == memory.user_id,
                models.WordBookMemoryWord.wordbook_id == memory.wordbook_id,
                models.WordBookMemoryWord.status == "unknown",
            )
        ).one()
        or 0
    )
    memory.known_count = known
    memory.unknown_count = unknown
    memory.total_count = _total_entries(session, memory.wordbook_id)
    memory.is_completed = bool(memory.total_count and memory.cursor_offset >= memory.total_count)


def progress_payload(session: Session, memory: models.WordBookMemory) -> dict:
    total = memory.total_count or _total_entries(session, memory.wordbook_id)
    seen = min(total, max(memory.cursor_offset, memory.known_count + memory.unknown_count))
    percent = round((seen / total) * 100, 1) if total else 0.0
    return {
        "total": total,
        "learned": memory.known_count,
        "unknown": memory.unknown_count,
        "cursor": memory.cursor_offset,
        "percent": percent,
        "label": f"{seen} / {total}",
        "completed": bool(memory.is_completed),
        "last_studied_at": memory.last_studied_at.isoformat() if memory.last_studied_at else None,
    }


def progress_snapshot(
    session: Session,
    wordbook_id: int,
    *,
    user_id: int | None = None,
    total: int | None = None,
) -> dict:
    """Read-only progress for list cards (does not create rows)."""
    uid = user_id if user_id is not None else security.get_current_user_id(required=False)
    total_n = int(total if total is not None else _total_entries(session, wordbook_id))
    empty = {
        "total": total_n,
        "learned": 0,
        "unknown": 0,
        "cursor": 0,
        "percent": 0.0,
        "label": f"0 / {total_n}",
        "completed": False,
        "last_studied_at": None,
    }
    if not uid:
        return empty
    row = session.exec(
        select(models.WordBookMemory).where(
            models.WordBookMemory.user_id == uid,
            models.WordBookMemory.wordbook_id == wordbook_id,
        )
    ).first()
    if not row:
        return empty
    payload = progress_payload(session, row)
    if total is not None:
        payload["total"] = total_n
        seen = min(total_n, max(payload["cursor"], payload["learned"] + payload["unknown"]))
        payload["percent"] = round((seen / total_n) * 100, 1) if total_n else 0.0
        payload["label"] = f"{seen} / {total_n}"
    return payload


def _upsert_memory_word(
    session: Session,
    *,
    user_id: int,
    wordbook_id: int,
    entry: models.WordBookEntry,
    status: str,
) -> None:
    row = session.exec(
        select(models.WordBookMemoryWord).where(
            models.WordBookMemoryWord.user_id == user_id,
            models.WordBookMemoryWord.entry_id == entry.id,
        )
    ).first()
    now = datetime.utcnow()
    if row:
        row.status = status
        row.word = entry.word
        row.wordbook_id = wordbook_id
        row.updated_at = now
        session.add(row)
    else:
        session.add(
            models.WordBookMemoryWord(
                user_id=user_id,
                wordbook_id=wordbook_id,
                entry_id=entry.id,
                word=entry.word,
                status=status,
                created_at=now,
                updated_at=now,
            )
        )


def study_feed(
    session: Session,
    wordbook_id: int,
    *,
    limit: int = 10,
    offset: int | None = None,
) -> dict:
    """Return a word page.

    - offset=None: resume from saved cursor (legacy / first open)
    - offset>=0: absolute page so clients can scroll up/down through the whole book
    """
    uid = _user_id()
    book = crud.get_wordbook(session, wordbook_id, user_id=uid)
    if not book:
        book = crud.get_wordbook(session, wordbook_id)
    if not book:
        raise KeyError("wordbook not found")

    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    total = _total_entries(session, wordbook_id)
    memory.total_count = total
    memory.last_studied_at = datetime.utcnow()
    memory.updated_at = datetime.utcnow()
    session.add(memory)
    session.commit()
    session.refresh(memory)

    limit = max(1, min(50, limit))
    # Browse by absolute offset; omit offset → open at saved resume position.
    # Clamp so we never land on an empty "past the end" page.
    if offset is None:
        cursor = int(memory.cursor_offset or 0)
        start = max(0, min(cursor, max(0, total - 1))) if total else 0
    else:
        start = max(0, min(int(offset), total))

    asset = _json_asset_for_wordbook(session, wordbook_id)
    if asset:
        page, total = wordbook_json_store.slice_entries(asset, start, limit)
        words = [str(e.get("word") or "") for e in page]
        starred_words: set[str] = set()
        if words:
            rows = session.exec(
                select(models.WordBookMemoryWord.word).where(
                    models.WordBookMemoryWord.user_id == uid,
                    models.WordBookMemoryWord.wordbook_id == wordbook_id,
                    models.WordBookMemoryWord.word.in_(words),
                    models.WordBookMemoryWord.status == "unknown",
                )
            ).all()
            starred_words = {str(x) for x in rows}
        items = [
            {
                "id": VIRTUAL_ID_BASE + start + i,
                "word": e.get("word") or "",
                "pronunciation": e.get("pronunciation") or "",
                "translation": e.get("translation") or e.get("definition") or "",
                "definition": e.get("definition") or "",
                "starred": (e.get("word") or "") in starred_words,
                "offset": start + i,
                "index": start + i + 1,
                "source": "json",
            }
            for i, e in enumerate(page)
        ]
    else:
        entries = session.exec(
            select(models.WordBookEntry)
            .where(models.WordBookEntry.wordbook_id == wordbook_id)
            .order_by(models.WordBookEntry.id.asc())
            .offset(start)
            .limit(limit)
        ).all()
        entry_ids = [e.id for e in entries]
        starred_ids: set[int] = set()
        if entry_ids:
            rows = session.exec(
                select(models.WordBookMemoryWord.entry_id).where(
                    models.WordBookMemoryWord.user_id == uid,
                    models.WordBookMemoryWord.entry_id.in_(entry_ids),
                    models.WordBookMemoryWord.status == "unknown",
                )
            ).all()
            starred_ids = {int(x) for x in rows}
        items = [
            {
                "id": e.id,
                "word": e.word,
                "pronunciation": e.pronunciation or "",
                "translation": e.translation or e.definition or "",
                "definition": e.definition or "",
                "starred": e.id in starred_ids,
                "offset": start + i,
                "index": start + i + 1,
                "source": "sql",
            }
            for i, e in enumerate(entries)
        ]

    end = start + len(items)
    return {
        "wordbook_id": wordbook_id,
        "name": book.name,
        "items": items,
        "offset": start,
        "limit": limit,
        "total": total,
        "progress": progress_payload(session, memory),
        "resume_offset": int(memory.cursor_offset or 0),
        "has_more": end < total,
        "has_more_after": end < total,
        "has_more_before": start > 0,
    }


def save_cursor(
    session: Session,
    wordbook_id: int,
    cursor: int,
) -> dict:
    """Persist resume position without forcing known/unknown marks."""
    uid = _user_id()
    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    total = _total_entries(session, wordbook_id)
    memory.total_count = total
    memory.cursor_offset = max(0, min(int(cursor), max(0, total - 1) if total else 0))
    memory.is_completed = bool(total and memory.cursor_offset >= max(0, total - 1))
    memory.last_studied_at = datetime.utcnow()
    memory.updated_at = datetime.utcnow()
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return {"ok": True, "progress": progress_payload(session, memory)}


def _resolve_entry(
    session: Session,
    wordbook_id: int,
    entry_id: int,
) -> models.WordBookEntry | None:
    entry = session.get(models.WordBookEntry, entry_id)
    if entry and entry.wordbook_id == wordbook_id:
        return entry
    if entry_id < VIRTUAL_ID_BASE:
        return None
    offset = int(entry_id) - VIRTUAL_ID_BASE
    asset = _json_asset_for_wordbook(session, wordbook_id)
    if not asset:
        return None
    entries = wordbook_json_store.load_entries(asset)
    if offset < 0 or offset >= len(entries):
        return None
    raw = entries[offset]
    return _ensure_sparse_entry(
        session,
        wordbook_id,
        word=str(raw.get("word") or ""),
        translation=str(raw.get("translation") or ""),
        pronunciation=str(raw.get("pronunciation") or ""),
        definition=str(raw.get("definition") or ""),
    )


def star_entry(
    session: Session,
    wordbook_id: int,
    entry_id: int,
    *,
    starred: bool = True,
) -> dict:
    uid = _user_id()
    book = crud.get_wordbook(session, wordbook_id) or crud.get_wordbook(session, wordbook_id, user_id=uid)
    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    entry = _resolve_entry(session, wordbook_id, entry_id)
    if not entry:
        raise KeyError("entry not found")

    if starred:
        _upsert_memory_word(
            session,
            user_id=uid,
            wordbook_id=wordbook_id,
            entry=entry,
            status="unknown",
        )
        word_data = dictionary.lookup_word_fast(entry.word, session=session)
        crud.save_vocab_with_context(
            session,
            {
                **word_data,
                "word": entry.word,
                "definition": entry.definition or word_data.get("definition") or "",
                "translation": entry.translation or word_data.get("translation"),
                "pronunciation": entry.pronunciation or word_data.get("pronunciation"),
                "part_of_speech": entry.part_of_speech or word_data.get("part_of_speech"),
                "example": entry.example,
                "source_platform": "wordbook",
                "source_video_id": f"wordbook-{wordbook_id}",
                "source_title": book.name if book else "词书",
                "wordbook_id": wordbook_id,
            },
        )
    else:
        _upsert_memory_word(
            session,
            user_id=uid,
            wordbook_id=wordbook_id,
            entry=entry,
            status="known",
        )
        card = crud.find_vocab_by_word(session, entry.word)
        if card:
            crud.delete_vocab_card(session, card)

    _recount_memory(session, memory)
    memory.last_studied_at = datetime.utcnow()
    memory.updated_at = datetime.utcnow()
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return {"ok": True, "starred": starred, "progress": progress_payload(session, memory)}


def commit_batch(
    session: Session,
    wordbook_id: int,
    entry_ids: list[int],
    starred_ids: list[int],
) -> dict:
    """Persist batch memory: starred → unknown; rest → known; advance cursor."""
    uid = _user_id()
    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    if not entry_ids:
        return {"ok": True, "progress": progress_payload(session, memory)}

    book = crud.get_wordbook(session, wordbook_id)
    starred_set = {int(x) for x in starred_ids or []}
    unique_ids: list[int] = []
    seen: set[int] = set()
    for eid in entry_ids:
        eid = int(eid)
        if eid in seen:
            continue
        seen.add(eid)
        unique_ids.append(eid)

    last_entry_id = memory.last_entry_id
    for eid in unique_ids:
        entry = _resolve_entry(session, wordbook_id, eid)
        if not entry:
            continue
        status = "unknown" if eid in starred_set else "known"
        _upsert_memory_word(
            session,
            user_id=uid,
            wordbook_id=wordbook_id,
            entry=entry,
            status=status,
        )
        last_entry_id = entry.id
        if status == "unknown":
            word_data = dictionary.lookup_word_fast(entry.word, session=session)
            crud.save_vocab_with_context(
                session,
                {
                    **word_data,
                    "word": entry.word,
                    "definition": entry.definition or word_data.get("definition") or "",
                    "translation": entry.translation or word_data.get("translation"),
                    "pronunciation": entry.pronunciation or word_data.get("pronunciation"),
                    "source_platform": "wordbook",
                    "source_video_id": f"wordbook-{wordbook_id}",
                    "source_title": book.name if book else "词书",
                    "wordbook_id": wordbook_id,
                },
            )

    total = _total_entries(session, wordbook_id)
    memory.cursor_offset = min(
        max(0, total - 1) if total else 0,
        memory.cursor_offset + len(unique_ids),
    )
    memory.last_entry_id = last_entry_id
    _recount_memory(session, memory)
    memory.last_studied_at = datetime.utcnow()
    memory.updated_at = datetime.utcnow()
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return {"ok": True, "progress": progress_payload(session, memory)}
