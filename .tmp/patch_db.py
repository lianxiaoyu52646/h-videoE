from pathlib import Path

# models.py: index due
p = Path(r"D:\lian\praPro\h-videoE\app\models.py")
text = p.read_text(encoding="utf-8")
old = '    due: datetime = Field(default_factory=datetime.utcnow)'
new = '    due: datetime = Field(default_factory=datetime.utcnow, index=True)'
n = text.count(old)
if n != 1:
    raise SystemExit(f"models due count={n}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("ok models.py due index")

# database.py: sqlite + generic indexes
p = Path(r"D:\lian\praPro\h-videoE\app\database.py")
text = p.read_text(encoding="utf-8")
old = '        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_word ON vocabcard (user_id, word)")'
new = '''        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_word ON vocabcard (user_id, word)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_due ON vocabcard (user_id, due)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_id ON vocabcard (user_id, id)")'''
n = text.count(old)
if n != 1:
    raise SystemExit(f"sqlite index count={n}")
text = text.replace(old, new, 1)

old_init = '''def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if settings.is_sqlite:
        _migrate_sqlite_schema()
'''
new_init = '''def _ensure_vocab_perf_indexes() -> None:
    from sqlalchemy import text as sa_text

    stmts = (
        "CREATE INDEX IF NOT EXISTS ix_vocabcard_user_due ON vocabcard (user_id, due)",
        "CREATE INDEX IF NOT EXISTS ix_vocabcard_user_id ON vocabcard (user_id, id)",
    )
    try:
        with engine.begin() as conn:
            for stmt in stmts:
                conn.execute(sa_text(stmt))
    except Exception:
        pass


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if settings.is_sqlite:
        _migrate_sqlite_schema()
    else:
        _ensure_vocab_perf_indexes()
'''
n = text.count(old_init)
if n != 1:
    raise SystemExit(f"init_db count={n}")
text = text.replace(old_init, new_init, 1)
p.write_text(text, encoding="utf-8")
print("ok database.py")
