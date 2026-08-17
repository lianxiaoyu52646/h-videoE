from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\database.py")
text = p.read_text(encoding="utf-8")
old = '''def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if settings.is_sqlite:
        _migrate_sqlite_schema()
    else:
        _ensure_vocab_perf_indexes()
        _enable_sqlite_wal()
'''
new = '''def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if settings.is_sqlite:
        _migrate_sqlite_schema()
        _enable_sqlite_wal()
    else:
        _ensure_vocab_perf_indexes()
'''
n = text.count(old)
if n != 1:
    raise SystemExit(f"init_db count={n}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("fixed init_db")
