from __future__ import annotations

from app import models
from app.services import dictionary
from sqlmodel import Session


def wrap_ipa(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return text
    if text.startswith("/") or text.startswith("["):
        return text
    return f"/{text}/"


def format_pronunciation(
    *,
    us: str | None = None,
    uk: str | None = None,
    raw: str | None = None,
) -> str | None:
    parts: list[str] = []
    if us:
        parts.append(f"美 {wrap_ipa(us)}")
    if uk and uk.strip() and uk.strip() != (us or "").strip():
        parts.append(f"英 {wrap_ipa(uk)}")
    elif uk and not us:
        parts.append(wrap_ipa(uk))
    if parts:
        return "  ".join(parts)
    if raw:
        wrapped = wrap_ipa(raw)
        return wrapped or None
    return None


def enrich_wordbook_entries_pronunciation(
    session: Session,
    entries: list[models.WordBookEntry],
) -> None:
    """仅使用本地词典缓存补音标，不在列表接口里触发在线查询。"""
    changed = False
    for entry in entries:
        if (entry.pronunciation or "").strip():
            continue
        payload = dictionary.lookup_word_fast(entry.word, session=session)
        pronunciation = (payload.get("pronunciation") or "").strip() or None
        if pronunciation:
            entry.pronunciation = pronunciation
            session.add(entry)
            changed = True
    if changed:
        session.commit()
