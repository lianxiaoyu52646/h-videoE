import sqlite3
from pathlib import Path
db = Path(r"D:\lian\praPro\h-videoE\db.sqlite3")
print("db exists", db.exists(), db.stat().st_size if db.exists() else 0)
if db.exists():
    conn = sqlite3.connect(str(db), timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_due ON vocabcard (user_id, due)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_id ON vocabcard (user_id, id)")
        conn.commit()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='vocabcard'")
        print("indexes", [r[0] for r in cur.fetchall()])
        cur.execute("SELECT COUNT(*) FROM vocabcard")
        print("vocab count", cur.fetchone()[0])
    finally:
        conn.close()
