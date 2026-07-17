"""
FSRS 间隔重复算法调度器
基于 fsrs 库实现智能复习调度
"""
from datetime import datetime, timedelta, timezone
from app.models import VocabCard


def _get_fsrs():
    try:
        from fsrs import Scheduler, Card, Rating
        return Scheduler, Card, Rating
    except ImportError:
        print("[fsrs] py-fsrs not installed, using fallback SM-2")
        return None


def create_new_card() -> dict:
    fsrs_types = _get_fsrs()
    if fsrs_types is None:
        return {}
    _, Card, _ = fsrs_types
    card = Card()
    return {
        "stability": card.stability,
        "difficulty": card.difficulty,
        "elapsed_days": 0,
        "scheduled_days": 0,
        "reps": 0,
        "lapses": 0,
        "state": 0,
        "last_review": None,
    }


def review_card(card: VocabCard, rating: int):
    fsrs_types = _get_fsrs()
    if fsrs_types is None:
        _fallback_sm2(card, rating)
        return

    FSRS, Card, Rating = fsrs_types

    fsrs_card = Card()
    # FSRS requires non-zero stability for review calculations.
    # For new cards (reps=0), use the Card() defaults directly.
    if card.reps > 0:
        fsrs_card.stability = card.stability if card.stability and card.stability > 0 else 0.1
        fsrs_card.difficulty = card.difficulty if card.difficulty and card.difficulty > 0 else 0.1
        fsrs_card.elapsed_days = card.elapsed_days or 0
        fsrs_card.scheduled_days = card.scheduled_days or 0
        fsrs_card.reps = card.reps
        fsrs_card.lapses = card.lapses or 0
        if card.last_review:
            fsrs_card.last_review = card.last_review.replace(tzinfo=timezone.utc)

    f = FSRS()
    mapping = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}
    fsrs_rating = mapping.get(rating, Rating.Good)

    # py-fsrs v6: review_card returns (card, review_log) tuple
    result = f.review_card(fsrs_card, fsrs_rating)
    if isinstance(result, tuple):
        updated = result[0]
    else:
        updated = result if isinstance(result, Card) else result.get("card", result)

    card.stability = getattr(updated, "stability", 0)
    card.difficulty = getattr(updated, "difficulty", 0)
    card.elapsed_days = getattr(updated, "elapsed_days", 0)
    card.scheduled_days = getattr(updated, "scheduled_days", 0)
    card.reps = getattr(updated, "reps", 0)
    card.lapses = getattr(updated, "lapses", 0)
    state_val = getattr(updated, "state", 0)
    try:
        card.state = int(state_val)
    except (TypeError, ValueError):
        card.state = 0
    card.last_review = datetime.now(timezone.utc)
    due = getattr(updated, "due", None)
    if due:
        card.due = due if isinstance(due, datetime) else datetime.now(timezone.utc)
    else:
        card.due = datetime.now(timezone.utc) + timedelta(days=max(1, card.scheduled_days))


def _fallback_sm2(card: VocabCard, quality: int):
    quality = max(0, min(5, quality + 1))
    card.reps = (card.reps or 0) + 1
    ease = 2.5
    ease = max(1.3, ease + 0.1 - (5 - quality) * 0.08)
    if card.reps == 1:
        interval = 1
    elif card.reps == 2:
        interval = 6
    else:
        interval = int((card.scheduled_days or 1) * ease)
    card.scheduled_days = max(1, interval)
    card.due = datetime.now(timezone.utc) + timedelta(days=card.scheduled_days)
    card.last_review = datetime.now(timezone.utc)
