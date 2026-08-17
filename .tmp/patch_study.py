from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\services\wordbook_study.py")
text = p.read_text(encoding="utf-8")

old_write = '''    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    total = _total_entries(session, wordbook_id)
    # Read path: avoid a Neon write on every scroll page (was a major latency source).
    if int(memory.total_count or 0) != int(total):
        memory.total_count = total
        memory.updated_at = datetime.utcnow()
        session.add(memory)
        session.commit()
        session.refresh(memory)
'''
new_write = '''    memory = get_or_create_memory(session, wordbook_id, user_id=uid)
    total = _total_entries(session, wordbook_id)
    # Read path: never write/refresh — live `total` is returned in the payload.
'''

old_json = '''                "translation": e.get("translation") or e.get("definition") or "",
                "definition": e.get("definition") or "",
                "starred": (e.get("word") or "") in starred_words,
'''
new_json = '''                "translation": e.get("translation") or e.get("definition") or "",
                "starred": (e.get("word") or "") in starred_words,
'''

old_sql = '''                "translation": e.translation or e.definition or "",
                "definition": e.definition or "",
                "starred": e.id in starred_ids,
'''
new_sql = '''                "translation": e.translation or e.definition or "",
                "starred": e.id in starred_ids,
'''

for label, old, new in [
    ("no_write_on_read", old_write, new_write),
    ("json_lean", old_json, new_json),
    ("sql_lean", old_sql, new_sql),
]:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label} count={n}")
    text = text.replace(old, new, 1)
    print("ok", label)

p.write_text(text, encoding="utf-8")
print("wrote wordbook_study.py")
