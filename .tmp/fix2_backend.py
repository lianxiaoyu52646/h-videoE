# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(r"D:\lian\praPro\h-videoE")

# ----- review.py -----
review_py = r'''from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app import crud, database, schemas

router = APIRouter(prefix='/api', tags=['review'])


def _plain_vocab_read(card) -> dict:
    """Light serializer for due-queue GET (skip N+1 context/review counts)."""
    data = card.model_dump()
    data.pop('contexts', None)
    data.pop('review_logs', None)
    if data.get('definition') is None:
        data['definition'] = ''
    data['contexts_count'] = int(data.get('contexts_count') or 0)
    data['review_count'] = int(data.get('review_count') or 0)
    return data


@router.post('/review', response_model=schemas.VocabRead)
def review_vocab(request: schemas.ReviewRequest, session: Session = Depends(database.session_dependency)):
    """Apply FSRS rating. Mobile UI maps 会→4 (Good), 不会→1 (Again)."""
    card = crud.review_vocab(session, request.vocab_id, request.rating)
    if not card:
        raise HTTPException(status_code=404, detail='Vocabulary card not found')
    # review_vocab() commits, which expires the ORM instance. Dumping the
    # expired object as VocabRead 500s (mobile toast: generic 请求失败).
    try:
        session.refresh(card)
    except Exception:
        pass
    return crud.vocab_to_read(session, card)


@router.get('/recommendations', response_model=list[schemas.VocabRead])
def recommendations(
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
    limit: int = Query(24, ge=1, le=80),
    session: Session = Depends(database.session_dependency),
):
    items = crud.get_due_vocab(
        session,
        datetime.utcnow(),
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
        limit=limit,
    )
    return [_plain_vocab_read(item) for item in items]
'''
(ROOT / "app/routers/review.py").write_text(review_py, encoding="utf-8")
print("wrote review.py")

# ----- crud.py: naive datetimes after FSRS -----
crud_path = ROOT / "app/crud.py"
crud = crud_path.read_text(encoding="utf-8")
old = """    due_before = card.due
    fsrs_scheduler.review_card(card, rating)
    log = models.ReviewLog("""
new = """    due_before = card.due
    fsrs_scheduler.review_card(card, rating)
    # SQLite DateTime rejects tz-aware values (py-fsrs returns UTC-aware).
    if card.due is not None and getattr(card.due, "tzinfo", None) is not None:
        card.due = card.due.astimezone(timezone.utc).replace(tzinfo=None)
    if card.last_review is not None and getattr(card.last_review, "tzinfo", None) is not None:
        card.last_review = card.last_review.astimezone(timezone.utc).replace(tzinfo=None)
    log = models.ReviewLog("""
if old not in crud:
    raise SystemExit("crud.py review_vocab marker not found")
crud = crud.replace(old, new, 1)

old2 = """    data = card.model_dump()
    data["contexts_count"] = session.exec(
        select(func.count(models.VocabContext.id)).where(models.VocabContext.vocab_id == card.id)
    ).one()
    data["review_count"] = session.exec(
        select(func.count(models.ReviewLog.id)).where(models.ReviewLog.vocab_id == card.id)
    ).one()
    return data"""
new2 = """    data = card.model_dump()
    data.pop("contexts", None)
    data.pop("review_logs", None)
    if data.get("definition") is None:
        data["definition"] = ""
    data["contexts_count"] = session.exec(
        select(func.count(models.VocabContext.id)).where(models.VocabContext.vocab_id == card.id)
    ).one()
    data["review_count"] = session.exec(
        select(func.count(models.ReviewLog.id)).where(models.ReviewLog.vocab_id == card.id)
    ).one()
    return data"""
if old2 not in crud:
    raise SystemExit("crud.py vocab_to_read marker not found")
crud = crud.replace(old2, new2, 1)
crud_path.write_text(crud, encoding="utf-8")
print("patched crud.py")

# ----- CSS -----
css_path = ROOT / "app/static/css/mobile.css"
css = css_path.read_text(encoding="utf-8")
css = css.replace(
    """.study-top {
  position: sticky;
  top: 58px;
  z-index: 12;
  transition: opacity 0.22s ease, transform 0.22s ease;
  display: grid;""",
    """.study-top {
  position: sticky;
  top: 58px;
  z-index: 12;
  min-height: 64px;
  transition: none;
  display: grid;""",
    1,
)
css = css.replace(
    """.study-top.is-away {
  opacity: 0;
  transform: translateY(-12px);
  pointer-events: none;
}""",
    """.study-top.is-away {
  opacity: 0;
  transform: translateY(-12px);
  pointer-events: none;
  transition: opacity 0.22s ease, transform 0.22s ease;
}""",
    1,
)
css = css.replace(
    """.study-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  contain: content;
}""",
    """.study-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  contain: content;
  min-height: 120px;
}""",
    1,
)
css = css.replace(
    """.view.active {
  display: block;
  animation: viewIn 0.28s ease both;
}""",
    """.view.active {
  display: block;
  animation: viewIn 0.28s ease both;
}
#view-books.view.active.is-study {
  animation: none;
}""",
    1,
)
css_path.write_text(css, encoding="utf-8")
print("patched mobile.css")

# ----- version bump -----
idx = ROOT / "app/static/m/index.html"
idx.write_text(idx.read_text(encoding="utf-8").replace("20260817.6", "20260817.7"), encoding="utf-8")
ver = ROOT / "app/static/m/app-version.json"
ver.write_text(ver.read_text(encoding="utf-8").replace("20260817.6", "20260817.7"), encoding="utf-8")
print("bumped version to 20260817.7")
print(idx.read_text(encoding="utf-8"))
print(ver.read_text(encoding="utf-8"))
