"""修复词书词条 translation/definition 重复或字段错位。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select

from app import database, models

CJK = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(text: str) -> bool:
    return bool(CJK.search(text or ""))


def repair_entry(entry: models.WordBookEntry) -> bool:
    translation = (entry.translation or "").strip()
    definition = (entry.definition or "").strip()
    changed = False

    if translation and definition and translation == definition:
        if _has_cjk(translation):
            if entry.definition:
                entry.definition = ""
                changed = True
        elif entry.translation:
            entry.translation = None
            changed = True
        return changed

    if translation and not _has_cjk(translation):
        if not definition:
            entry.definition = translation
            entry.translation = None
            changed = True
        elif _has_cjk(definition):
            entry.translation = definition
            entry.definition = translation
            changed = True
        elif definition == translation and entry.translation:
            entry.translation = None
            changed = True

    return changed


def repair_wordbook(wordbook_id: int) -> int:
    database.init_db()
    updated = 0
    with Session(database.engine) as session:
        entries = session.exec(
            select(models.WordBookEntry)
            .where(models.WordBookEntry.wordbook_id == wordbook_id)
            .order_by(models.WordBookEntry.word.asc())
        ).all()
        for entry in entries:
            if repair_entry(entry):
                session.add(entry)
                updated += 1
        session.commit()
    print(f"wordbook {wordbook_id}: repaired {updated} entries")
    return updated


if __name__ == "__main__":
    wid = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    repair_wordbook(wid)
