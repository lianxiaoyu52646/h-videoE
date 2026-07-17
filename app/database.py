from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings


def _sqlite_db_path() -> Path | None:
    if not settings.database_url.startswith("sqlite:///"):
        return None
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if not db_path or db_path == ":memory:":
        return None
    return Path(db_path)


def get_sqlite_db_path() -> Path | None:
    return _sqlite_db_path()


def _create_engine():
    sqlite_path = _sqlite_db_path()
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False, "timeout": 30} if settings.is_sqlite else {}
    eng = create_engine(
        settings.database_url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    if settings.is_sqlite:
        from sqlalchemy import event

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA busy_timeout=30000")
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                pass
            cursor.close()

    return eng


engine = _create_engine()

_VOCAB_COLUMNS = [
    ("translation", "TEXT"),
    ("source_platform", "TEXT"),
    ("source_video_id", "TEXT"),
    ("source_url", "TEXT"),
    ("source_title", "TEXT"),
    ("sentence", "TEXT"),
    ("sentence_translation", "TEXT"),
    ("timestamp", "REAL"),
    ("user_id", "INTEGER DEFAULT 1"),
    ("lemma", "TEXT"),
    ("wordbook_id", "INTEGER"),
]

_VIDEO_COLUMNS = [
    ("progress", "INTEGER"),
    ("status_message", "TEXT"),
    ("duration_seconds", "REAL"),
    ("user_id", "INTEGER DEFAULT 1"),
    ("active_job_id", "INTEGER"),
]

_READING_COLUMNS = [
    ("last_block_index", "INTEGER"),
    ("read_progress", "INTEGER"),
    ("source_type", "TEXT"),
    ("source_url", "TEXT"),
    ("source_filename", "TEXT"),
    ("user_id", "INTEGER DEFAULT 1"),
    ("active_job_id", "INTEGER"),
]

_READING_BLOCK_COLUMNS = [
    ("section_title", "TEXT"),
    ("text_hash", "TEXT"),
]

_READING_HIGHLIGHT_COLUMNS = [("user_id", "INTEGER DEFAULT 1")]
_READING_NOTE_COLUMNS = [("user_id", "INTEGER DEFAULT 1")]
_READING_BOOKMARK_COLUMNS = [("user_id", "INTEGER DEFAULT 1")]
_WORDBOOK_COLUMNS = [("deleted_at", "TEXT")]
_READING_DOCUMENT_COLUMNS = [("deleted_at", "TEXT")]


def _ensure_columns(cur: sqlite3.Cursor, table: str, columns: list[tuple[str, str]]) -> None:
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not cur.fetchone():
        return
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for name, column_type in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")


def _migrate_sqlite_schema() -> None:
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if not db_path:
        db_path = "./db.sqlite3"
    if db_path == ":memory:":
        return
    path = Path(db_path)
    if not path.exists():
        return

    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        _ensure_columns(cur, "vocabcard", _VOCAB_COLUMNS)
        _ensure_columns(cur, "video", _VIDEO_COLUMNS)
        _ensure_columns(cur, "readingdocument", _READING_COLUMNS)
        _ensure_columns(cur, "readingblock", _READING_BLOCK_COLUMNS)
        _ensure_columns(cur, "readinghighlight", _READING_HIGHLIGHT_COLUMNS)
        _ensure_columns(cur, "readingnote", _READING_NOTE_COLUMNS)
        _ensure_columns(cur, "readingbookmark", _READING_BOOKMARK_COLUMNS)
        _ensure_columns(cur, "wordbook", _WORDBOOK_COLUMNS)
        _ensure_columns(cur, "readingdocument", _READING_DOCUMENT_COLUMNS)

        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_readingblock_doc_order "
            "ON readingblock (document_id, order_index)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_readingblock_doc_has_translation "
            "ON readingblock (document_id) "
            "WHERE translation IS NOT NULL AND length(trim(translation)) > 0"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS ix_vocabcard_user_word ON vocabcard (user_id, word)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_video_user_created ON video (user_id, created_at)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_readingdocument_user_created "
            "ON readingdocument (user_id, created_at)"
        )

        for table in ("video", "readingdocument", "readinghighlight", "readingnote", "readingbookmark", "vocabcard"):
            cur.execute(f"UPDATE {table} SET user_id = 1 WHERE user_id IS NULL OR user_id = 0")

        conn.commit()
    finally:
        conn.close()


def _enable_sqlite_wal() -> None:
    db_path = _sqlite_db_path()
    if db_path is None or not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if settings.is_sqlite:
        _migrate_sqlite_schema()
        _enable_sqlite_wal()
    try:
        from app.services.reading_search import ensure_fts_schema

        ensure_fts_schema()
    except Exception:
        pass


def get_session():
    with Session(engine) as session:
        yield session


def session_dependency():
    yield from get_session()
