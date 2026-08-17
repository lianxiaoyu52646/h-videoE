from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\crud.py")
t = p.read_text(encoding="utf-8")
old = '''    # SQLite DateTime rejects tz-aware values (py-fsrs returns UTC-aware).
    if card.due is not None and getattr(card.due, "tzinfo", None) is not None:
        card.due = card.due.astimezone(timezone.utc).replace(tzinfo=None)
    if card.last_review is not None and getattr(card.last_review, "tzinfo", None) is not None:
        card.last_review = card.last_review.astimezone(timezone.utc).replace(tzinfo=None)
'''
new = '''    # SQLite DateTime rejects tz-aware values (py-fsrs returns UTC-aware).
    if due_before is not None and getattr(due_before, "tzinfo", None) is not None:
        due_before = due_before.astimezone(timezone.utc).replace(tzinfo=None)
    if card.due is not None and getattr(card.due, "tzinfo", None) is not None:
        card.due = card.due.astimezone(timezone.utc).replace(tzinfo=None)
    if card.last_review is not None and getattr(card.last_review, "tzinfo", None) is not None:
        card.last_review = card.last_review.astimezone(timezone.utc).replace(tzinfo=None)
'''
if old not in t:
    raise SystemExit('marker missing')
p.write_text(t.replace(old, new, 1), encoding='utf-8')
print('due_before naive ok')
