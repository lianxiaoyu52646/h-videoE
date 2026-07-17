"""批量补全词书缺失的中文释义（有道 suggest，适合 IELTS 等导入时无中文的词书）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select

from app import crud, database, models
from app.services.youdao_translator import lookup_word


def backfill_wordbook(wordbook_id: int, *, batch_size: int = 50) -> int:
    database.init_db()
    with Session(database.engine) as session:
        if not crud.get_wordbook(session, wordbook_id):
            raise SystemExit(f"wordbook {wordbook_id} not found")
        pending = [
            (entry.id, entry.word)
            for entry in session.exec(
                select(models.WordBookEntry)
                .where(models.WordBookEntry.wordbook_id == wordbook_id)
                .order_by(models.WordBookEntry.word.asc())
            ).all()
            if not (entry.translation or "").strip() and not (entry.definition or "").strip()
        ]

    total = len(pending)
    print(f"wordbook {wordbook_id}: {total} entries need translation")
    updated = 0
    batch_updates: list[tuple[int, str]] = []

    def flush_batch() -> None:
        nonlocal updated
        if not batch_updates:
            return
        with Session(database.engine) as session:
            for entry_id, translation in batch_updates:
                entry = session.get(models.WordBookEntry, entry_id)
                if not entry:
                    continue
                entry.translation = translation
                session.add(entry)
                updated += 1
            session.commit()
        batch_updates.clear()

    for index, (entry_id, word) in enumerate(pending, start=1):
        translation = lookup_word(word)
        if translation:
            batch_updates.append((entry_id, translation))
        if len(batch_updates) >= batch_size:
            flush_batch()
            print(f"  progress {index}/{total}, updated {updated}")
    flush_batch()
    print(f"done: updated {updated}/{total}")
    return updated


if __name__ == "__main__":
    wid = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    backfill_wordbook(wid)
