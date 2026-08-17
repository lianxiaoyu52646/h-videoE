# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path(r"D:\lian\praPro\h-videoE")
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    bak = p.with_suffix(p.suffix + f".bak-{stamp}")
    shutil.copy2(p, bak)
    print("backup", bak)

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"MISSING BLOCK: {label}\n---\n{old[:200]}")
    return text.replace(old, new, 1)

crud_path = ROOT / "app" / "crud.py"
backup(crud_path)
crud = crud_path.read_text(encoding="utf-8")
old = """def list_vocab(
    session: Session,
    source_video_id: str | None = None,
    *,
    wordbook_id: int | None = None,
    user_id: int | None = None,
):
    stmt = select(models.VocabItem).order_by(models.VocabItem.added_at.desc())
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    if wordbook_id is not None:
        stmt = stmt.where(models.VocabItem.wordbook_id == wordbook_id)
    items = session.exec(stmt).all()
    if source_video_id:
        items = [item for item in items if _card_matches_source(session, item, source_video_id)]
    return items
"""
new = """def list_vocab(
    session: Session,
    source_video_id: str | None = None,
    *,
    wordbook_id: int | None = None,
    user_id: int | None = None,
):
    stmt = select(models.VocabItem).order_by(models.VocabItem.added_at.desc())
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    if wordbook_id is not None:
        stmt = stmt.where(models.VocabItem.wordbook_id == wordbook_id)
    items = session.exec(stmt).all()
    if source_video_id:
        items = [item for item in items if _card_matches_source(session, item, source_video_id)]
    return items


def count_vocab(session: Session, user_id: int | None = None) -> int:
    stmt = select(func.count(models.VocabItem.id))
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    return int(session.exec(stmt).one() or 0)


def list_vocab_page(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 24,
    user_id: int | None = None,
):
    \"\"\"Stable id-order page for vocab-book study feed.\"\"\"
    limit = max(1, min(100, int(limit or 24)))
    offset = max(0, int(offset or 0))
    stmt = (
        select(models.VocabItem)
        .order_by(models.VocabItem.id.asc())
        .offset(offset)
        .limit(limit)
    )
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    return list(session.exec(stmt).all())
"""
crud = replace_once(crud, old, new, "list_vocab")
crud_path.write_text(crud, encoding="utf-8")
print("patched crud.py")

vocab_path = ROOT / "app" / "routers" / "vocabulary.py"
backup(vocab_path)
vocab = vocab_path.read_text(encoding="utf-8")
old = """from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app import crud, models, schemas
from app import database
from app.services import dictionary, translator
"""
new = """import json
from datetime import datetime
from pathlib import Path as _Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select
from app import crud, models, schemas, security
from app import database
from app.services import dictionary, translator
"""
vocab = replace_once(vocab, old, new, "vocabulary imports")

old = """@router.get("/api/vocab", response_model=list[schemas.VocabRead])
def list_vocab(
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    items = crud.list_vocab(session, source_video_id=source_video_id, wordbook_id=wordbook_id)
    return crud.vocab_to_read_many(session, items)
"""
new = """@router.get("/api/vocab", response_model=list[schemas.VocabRead])
def list_vocab(
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    items = crud.list_vocab(session, source_video_id=source_video_id, wordbook_id=wordbook_id)
    return crud.vocab_to_read_many(session, items)


class VocabStudyCursorIn(BaseModel):
    cursor: int = 0


class VocabStudyStarIn(BaseModel):
    vocab_id: int
    starred: bool = True


def _vocab_cursor_path() -> _Path:
    return _Path("books_data") / "vocab_study_cursors.json"


def _read_vocab_cursor(session: Session) -> int:
    uid = str(security.get_current_user_id(required=False) or 0)
    try:
        data = json.loads(_vocab_cursor_path().read_text(encoding="utf-8"))
        return int(data.get(uid) or 0)
    except Exception:
        return 0


def _vocab_progress(total: int, cursor: int) -> dict:
    total_n = max(0, int(total or 0))
    cursor_n = max(0, min(int(cursor or 0), max(0, total_n - 1) if total_n else 0))
    display = min(total_n, cursor_n + 1) if total_n else 0
    percent = round((display / total_n) * 100, 1) if total_n else 0.0
    return {
        "total": total_n,
        "learned": 0,
        "unknown": total_n,
        "cursor": cursor_n,
        "percent": percent,
        "label": f"{display} / {total_n}",
        "completed": bool(total_n and cursor_n >= max(0, total_n - 1)),
        "last_studied_at": None,
    }


def _write_vocab_cursor(session: Session, cursor: int, total: int) -> dict:
    uid = str(security.get_current_user_id(required=True))
    total_n = max(0, int(total or 0))
    cursor_n = max(0, min(int(cursor or 0), max(0, total_n - 1) if total_n else 0))
    path = _vocab_cursor_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data[uid] = cursor_n
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    payload = _vocab_progress(total_n, cursor_n)
    payload["last_studied_at"] = datetime.utcnow().isoformat()
    return payload


@router.get("/api/vocab/study-feed")
def vocab_study_feed(
    limit: int = Query(24, ge=1, le=100),
    offset: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    total = crud.count_vocab(session)
    saved = _read_vocab_cursor(session)
    start = saved if offset is None else max(0, int(offset))
    if total:
        start = min(start, max(0, total - 1))
    items_raw = crud.list_vocab_page(session, offset=start, limit=limit)
    items = []
    for i, card in enumerate(items_raw):
        items.append({
            "id": card.id,
            "word": card.word,
            "pronunciation": card.pronunciation or "",
            "translation": card.translation or card.definition or "",
            "definition": card.definition or "",
            "starred": True,
            "offset": start + i,
            "index": start + i + 1,
            "source": "vocab",
        })
    end = start + len(items)
    progress = _vocab_progress(total, start)
    return {
        "wordbook_id": 0,
        "name": "生词书",
        "items": items,
        "offset": start,
        "limit": limit,
        "total": total,
        "progress": progress,
        "resume_offset": saved,
        "has_more": end < total,
        "has_more_after": end < total,
        "has_more_before": start > 0,
    }


@router.post("/api/vocab/study-cursor")
def vocab_study_cursor(
    payload: VocabStudyCursorIn,
    session: Session = Depends(database.session_dependency),
):
    total = crud.count_vocab(session)
    progress = _write_vocab_cursor(session, payload.cursor, total)
    return {"ok": True, "progress": progress}


@router.post("/api/vocab/study-star")
def vocab_study_star(
    payload: VocabStudyStarIn,
    session: Session = Depends(database.session_dependency),
):
    card = crud.get_vocab_card(session, payload.vocab_id)
    if payload.starred:
        if not card:
            raise HTTPException(status_code=404, detail="Vocabulary card not found")
        return {"ok": True, "starred": True}
    if card:
        crud.delete_vocab_card(session, card)
        session.commit()
    return {"ok": True, "starred": False}
"""
vocab = replace_once(vocab, old, new, "list_vocab route")
vocab_path.write_text(vocab, encoding="utf-8")
print("patched vocabulary.py")
print("backend ok")
