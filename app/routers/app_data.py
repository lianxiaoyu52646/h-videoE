from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session
from starlette.background import BackgroundTask

from app import crud, database

router = APIRouter(prefix="/api/app", tags=["app-data"])


def _cleanup_dir(path: Path) -> None:
    for item in path.glob("*"):
        item.unlink(missing_ok=True)
    path.rmdir()


def _export_vocab(session: Session) -> list[dict]:
    return [crud.vocab_to_read(session, item) for item in crud.list_vocab(session)]


def _export_wordbooks(session: Session) -> list[dict]:
    items: list[dict] = []
    for wordbook in crud.list_wordbooks(session):
        items.append(
            {
                "book": crud.wordbook_to_read(session, wordbook),
                "entries": [entry.model_dump() for entry in crud.list_wordbook_entries(session, wordbook.id)],
            }
        )
    return items


def _json_download(payload: object, filename: str) -> Response:
    content = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/vocab")
def export_vocab(session: Session = Depends(database.session_dependency)):
    return _json_download(_export_vocab(session), "videoenglish-vocab.json")


@router.get("/backup")
def export_backup(session: Session = Depends(database.session_dependency)):
    db_path = database.get_sqlite_db_path()
    if not db_path or not db_path.exists():
        raise HTTPException(status_code=400, detail="当前不是可备份的本地 SQLite 数据库")

    temp_dir = Path(tempfile.mkdtemp(prefix="videoenglish-backup-"))
    sqlite_snapshot = temp_dir / "videoenglish.sqlite3"
    zip_path = temp_dir / f"videoenglish-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"

    source = sqlite3.connect(str(db_path))
    try:
        target = sqlite3.connect(str(sqlite_snapshot))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    vocab_payload = _export_vocab(session)
    wordbooks_payload = _export_wordbooks(session)
    meta_payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "database": sqlite_snapshot.name,
        "vocab_count": len(vocab_payload),
        "wordbook_count": len(wordbooks_payload),
    }

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(sqlite_snapshot, arcname=sqlite_snapshot.name)
        zf.writestr("vocab.json", json.dumps(vocab_payload, ensure_ascii=False, default=str, indent=2))
        zf.writestr("wordbooks.json", json.dumps(wordbooks_payload, ensure_ascii=False, default=str, indent=2))
        zf.writestr("meta.json", json.dumps(meta_payload, ensure_ascii=False, default=str, indent=2))

    return Response(
        content=zip_path.read_bytes(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_path.name}"'},
        background=BackgroundTask(_cleanup_dir, temp_dir),
    )
