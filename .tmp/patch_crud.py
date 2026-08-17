from pathlib import Path

p = Path(r"D:\lian\praPro\h-videoE\app\crud.py")
text = p.read_text(encoding="utf-8")

old_page = '''def list_vocab_page(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 24,
    user_id: int | None = None,
):
    """Stable id-order page for vocab-book study feed."""
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
'''

new_page = '''def list_vocab_page(
    session: Session,
    *,
    offset: int = 0,
    limit: int = 24,
    user_id: int | None = None,
):
    """Stable id-order page for vocab-book study feed (lean columns)."""
    from sqlalchemy.orm import load_only

    limit = max(1, min(100, int(limit or 24)))
    offset = max(0, int(offset or 0))
    stmt = (
        select(models.VocabItem)
        .options(
            load_only(
                models.VocabItem.id,
                models.VocabItem.word,
                models.VocabItem.pronunciation,
                models.VocabItem.translation,
                models.VocabItem.definition,
            )
        )
        .order_by(models.VocabItem.id.asc())
        .offset(offset)
        .limit(limit)
    )
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    return list(session.exec(stmt).all())
'''

old_due = '''def get_due_vocab(
    session: Session,
    now: datetime,
    source_video_id: str | None = None,
    *,
    wordbook_id: int | None = None,
    user_id: int | None = None,
):
    """Return all due cards for FSRS practice queue (no count limit)."""
    stmt = select(models.VocabItem).where(models.VocabItem.due <= now)
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    if wordbook_id is not None:
        stmt = stmt.where(models.VocabItem.wordbook_id == wordbook_id)
    items = session.exec(stmt.order_by(models.VocabItem.due.asc())).all()
    if source_video_id:
        items = [item for item in items if _card_matches_source(session, item, source_video_id)]
    return items
'''

new_due = '''def get_due_vocab(
    session: Session,
    now: datetime,
    source_video_id: str | None = None,
    *,
    wordbook_id: int | None = None,
    user_id: int | None = None,
    limit: int | None = 24,
):
    """Return due cards for FSRS practice queue (default cap 24)."""
    cap = None if not limit else max(1, min(80, int(limit)))
    stmt = select(models.VocabItem).where(models.VocabItem.due <= now)
    stmt = _apply_user_scope(stmt, models.VocabItem, user_id)
    if wordbook_id is not None:
        stmt = stmt.where(models.VocabItem.wordbook_id == wordbook_id)
    stmt = stmt.order_by(models.VocabItem.due.asc())
    if source_video_id:
        items = session.exec(stmt).all()
        items = [item for item in items if _card_matches_source(session, item, source_video_id)]
        return items[:cap] if cap else items
    if cap:
        stmt = stmt.limit(cap)
    return list(session.exec(stmt).all())
'''

old_rev = '''    session.add(card)
    session.commit()
    session.refresh(card)
    log = models.ReviewLog(
        user_id=card.user_id,
        vocab_id=card.id,
        rating=rating,
        due_before=due_before,
        due_after=card.due,
        scheduled_days_after=card.scheduled_days,
        stability_after=card.stability,
        difficulty_after=card.difficulty,
    )
    session.add(log)
    session.commit()
    session.refresh(card)
    return card
'''

new_rev = '''    log = models.ReviewLog(
        user_id=card.user_id,
        vocab_id=card.id,
        rating=rating,
        due_before=due_before,
        due_after=card.due,
        scheduled_days_after=card.scheduled_days,
        stability_after=card.stability,
        difficulty_after=card.difficulty,
    )
    session.add(card)
    session.add(log)
    session.commit()
    return card
'''

for label, old, new in [
    ("list_vocab_page", old_page, new_page),
    ("get_due_vocab", old_due, new_due),
    ("review_vocab_commit", old_rev, new_rev),
]:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label} count={n}")
    text = text.replace(old, new, 1)
    print("ok", label)

p.write_text(text, encoding="utf-8")
print("wrote crud.py", p.stat().st_size)
