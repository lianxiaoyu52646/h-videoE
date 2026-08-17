from pathlib import Path

p = Path(r"D:\lian\praPro\h-videoE\app\routers\vocabulary.py")
text = p.read_text(encoding="utf-8")

old = '''    total = crud.count_vocab(session)
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
'''

new = '''    total = crud.count_vocab(session)
    if offset is None:
        saved = _read_vocab_cursor(session)
        start = saved
    else:
        start = max(0, int(offset))
        saved = start
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
            "starred": True,
            "offset": start + i,
            "index": start + i + 1,
        })
'''

n = text.count(old)
if n != 1:
    raise SystemExit(f"vocab feed count={n}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("ok vocabulary.py")
