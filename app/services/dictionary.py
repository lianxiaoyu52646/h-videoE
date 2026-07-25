"""
词典查询服务。

- 快查：本地 JSON 词包 + ECDICT SQLite + 词书 + 生词缓存，优先毫秒级返回
- 补全：有道中文释义 + dictionaryapi.dev 英文释义
"""
from datetime import datetime
import logging
from functools import lru_cache
from typing import Callable, Optional

import httpx
from sqlmodel import Session, select

from app import database, models, security
from app.services.dictionary_engine import DictionaryEngine, candidate_words, normalize_word
from app.services.youdao_translator import lookup_word as youdao_lookup_word
from app.config import settings

logger = logging.getLogger(__name__)

_ENGINE = DictionaryEngine(settings.bundled_dictionary_dir, settings.user_dictionary_dir)


def _empty_lookup(word: str = "") -> dict:
    return {
        "word": word,
        "lemma": word or None,
        "definition": "",
        "pronunciation": None,
        "part_of_speech": None,
        "example": None,
        "translation": None,
        "youdao_translation": None,
        "lookup_source": "miss",
        "matched_word": word or None,
        "suggestions": [],
        "pending_enrichment": False,
    }


def _payload_score(payload: dict) -> int:
    score = 0
    for key in (
        "translation",
        "youdao_translation",
        "definition",
        "pronunciation",
        "part_of_speech",
        "example",
    ):
        if payload.get(key):
            score += 1
    return score


def _lookup_source_priority(source: str | None) -> int:
    if source == "wordbook":
        return 40
    if source == "vocab":
        return 30
    if source == "online-cache":
        return 20
    if source:
        return 10
    return 0


def _needs_enrichment(payload: dict) -> bool:
    has_translation = bool(payload.get("translation") or payload.get("youdao_translation"))
    has_definition = bool(payload.get("definition"))
    return not (has_translation and has_definition)


def _run_with_session(session: Session | None, fn: Callable[[Session], dict]) -> dict:
    if session is not None:
        return fn(session)
    with Session(database.engine) as owned:
        return fn(owned)


def _active_user_id() -> int | None:
    return security.get_current_user_id(required=False)


def _cache_row_to_payload(row: models.DictionaryEntryCache) -> dict:
    payload = dict(row.entry_json or {})
    payload.setdefault("word", row.word)
    payload.setdefault("lemma", row.lemma or payload.get("word") or row.word)
    payload.setdefault("lookup_source", row.source_name)
    payload.setdefault("source_name", row.source_name)
    return payload


def _to_payload(
    *,
    word: str,
    lemma: str | None = None,
    definition: str = "",
    pronunciation: str | None = None,
    part_of_speech: str | None = None,
    example: str | None = None,
    translation: str | None = None,
    youdao_translation: str | None = None,
    lookup_source: str,
) -> dict:
    payload = _empty_lookup(word)
    payload.update(
        {
            "word": word,
            "lemma": lemma or word,
            "definition": definition or "",
            "pronunciation": pronunciation,
            "part_of_speech": part_of_speech,
            "example": example,
            "translation": translation,
            "youdao_translation": youdao_translation,
            "lookup_source": lookup_source,
            "matched_word": word,
        }
    )
    return payload


def _load_from_cache(session: Session, candidate: str) -> dict | None:
    stmt = select(models.DictionaryEntryCache).where(
        (models.DictionaryEntryCache.word == candidate) | (models.DictionaryEntryCache.lemma == candidate)
    )
    row = session.exec(stmt.order_by(models.DictionaryEntryCache.updated_at.desc())).first()
    return _cache_row_to_payload(row) if row else None


def _load_from_wordbook(session: Session, candidate: str) -> dict | None:
    stmt = select(models.WordBookEntry).where(
        (models.WordBookEntry.word == candidate) | (models.WordBookEntry.lemma == candidate)
    )
    user_id = _active_user_id()
    if user_id is not None:
        stmt = stmt.join(models.WordBook, models.WordBook.id == models.WordBookEntry.wordbook_id).where(
            models.WordBook.user_id == user_id,
            models.WordBook.deleted_at.is_(None),
        )
    row = session.exec(stmt).first()
    if not row:
        return None
    return _to_payload(
        word=row.word,
        lemma=row.lemma,
        definition=row.definition or "",
        pronunciation=row.pronunciation,
        part_of_speech=row.part_of_speech,
        example=row.example,
        translation=row.translation,
        lookup_source="wordbook",
    )


def _load_from_vocab(session: Session, candidate: str) -> dict | None:
    stmt = select(models.VocabItem).where(
        (models.VocabItem.word == candidate) | (models.VocabItem.lemma == candidate)
    )
    user_id = _active_user_id()
    if user_id is not None:
        stmt = stmt.where(models.VocabItem.user_id == user_id)
    row = session.exec(stmt).first()
    if not row:
        return None
    return _to_payload(
        word=row.word,
        lemma=row.lemma,
        definition=row.definition or "",
        pronunciation=row.pronunciation,
        part_of_speech=row.part_of_speech,
        example=row.example,
        translation=row.translation,
        lookup_source="vocab",
    )


def _merge_local_hits(query_word: str, hits: list[dict]) -> dict:
    merged = _empty_lookup(query_word)
    for hit in sorted(
        hits,
        key=lambda item: (
            _lookup_source_priority(item.get("lookup_source")),
            _payload_score(item),
            -(item.get("_candidate_index") or 0),
        ),
    ):
        if hit.get("word"):
            merged["word"] = hit["word"]
        if hit.get("lemma"):
            merged["lemma"] = hit["lemma"]
        if hit.get("matched_word"):
            merged["matched_word"] = hit["matched_word"]
        if hit.get("lookup_source"):
            merged["lookup_source"] = hit["lookup_source"]
        for key in (
            "definition",
            "pronunciation",
            "part_of_speech",
            "example",
            "translation",
            "youdao_translation",
        ):
            if hit.get(key):
                merged[key] = hit[key]

    merged["word"] = merged.get("word") or query_word
    merged["lemma"] = merged.get("lemma") or merged["word"] or query_word
    merged["matched_word"] = merged.get("matched_word") or merged["word"] or query_word
    return merged


def _local_payload(session: Session, word: str) -> dict | None:
    hits: list[dict] = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()

    def collect(payload: dict | None, candidate: str, candidate_index: int) -> None:
        if not payload:
            return
        entry = dict(payload)
        entry["matched_word"] = entry.get("matched_word") or candidate
        entry["_candidate_index"] = candidate_index
        fingerprint = (
            entry.get("lookup_source"),
            entry.get("word"),
            entry.get("lemma"),
            entry.get("matched_word"),
        )
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        hits.append(entry)

    for candidate_index, candidate in enumerate(candidate_words(word)):
        collect(_load_from_cache(session, candidate), candidate, candidate_index)
        collect(_load_from_wordbook(session, candidate), candidate, candidate_index)
        collect(_load_from_vocab(session, candidate), candidate, candidate_index)
        collect(_ENGINE.lookup_local(candidate), candidate, candidate_index)

    if not hits:
        return None
    return _merge_local_hits(word, hits)


def _collect_suggestions(session: Session, word: str, limit: int = 8) -> list[str]:
    suggestions: list[str] = []
    seen: set[str] = set()

    def add(item: str | None) -> None:
        normalized = normalize_word(item or "")
        if normalized and normalized not in seen:
            seen.add(normalized)
            suggestions.append(normalized)

    for item in _ENGINE.suggest(word, limit=limit):
        add(item)

    for model, field in (
        (models.DictionaryEntryCache, models.DictionaryEntryCache.word),
        (models.WordBookEntry, models.WordBookEntry.word),
        (models.VocabItem, models.VocabItem.word),
    ):
        stmt = select(field).where(field.like(f"{word}%")).limit(limit * 2)
        if model is models.WordBookEntry:
            user_id = _active_user_id()
            if user_id is not None:
                stmt = stmt.join(models.WordBook, models.WordBook.id == models.WordBookEntry.wordbook_id).where(
                    models.WordBook.user_id == user_id,
                    models.WordBook.deleted_at.is_(None),
                )
        elif hasattr(model, "user_id"):
            user_id = _active_user_id()
            if user_id is not None:
                stmt = stmt.where(model.user_id == user_id)
        for row in session.exec(stmt).all():
            add(row)
            if len(suggestions) >= limit:
                return suggestions
    return suggestions[:limit]


def _save_cache(session: Session, payload: dict, *, source_name: str = "online-cache") -> None:
    word = normalize_word(payload.get("word") or "")
    if not word:
        return
    row = session.exec(
        select(models.DictionaryEntryCache).where(
            models.DictionaryEntryCache.word == word,
            models.DictionaryEntryCache.source_name == source_name,
        )
    ).first()
    if not row:
        row = models.DictionaryEntryCache(word=word, lemma=payload.get("lemma") or word, source_name=source_name)
    row.lemma = normalize_word(payload.get("lemma") or word) or word
    row.entry_json = {
        "word": word,
        "lemma": row.lemma,
        "definition": payload.get("definition") or "",
        "pronunciation": payload.get("pronunciation"),
        "part_of_speech": payload.get("part_of_speech"),
        "example": payload.get("example"),
        "translation": payload.get("translation"),
        "youdao_translation": payload.get("youdao_translation"),
        "lookup_source": source_name,
        "matched_word": payload.get("matched_word") or word,
    }
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()


def _merge_payload(base: dict, enriched: dict) -> dict:
    merged = dict(base)
    for key in ("definition", "pronunciation", "part_of_speech", "example"):
        if not merged.get(key) and enriched.get(key):
            merged[key] = enriched[key]

    if enriched.get("youdao_translation"):
        merged["youdao_translation"] = enriched["youdao_translation"]
    if not merged.get("translation") and enriched.get("translation"):
        merged["translation"] = enriched["translation"]
    if merged.get("lookup_source") == "miss":
        merged["lookup_source"] = enriched.get("lookup_source", "online-cache")
    merged["pending_enrichment"] = False
    return merged


def lookup_word_fast(word: str, session: Session | None = None) -> dict:
    normalized = normalize_word(word)
    if not normalized:
        return _empty_lookup("")

    def _lookup(db: Session) -> dict:
        payload = _local_payload(db, normalized) or _empty_lookup(normalized)
        payload.setdefault("word", normalized)
        payload.setdefault("lemma", payload.get("word") or normalized)
        payload["matched_word"] = payload.get("matched_word") or normalized
        payload["lookup_source"] = payload.get("lookup_source") or "miss"
        payload["suggestions"] = _collect_suggestions(db, normalized)
        payload["pending_enrichment"] = _needs_enrichment(payload)
        return payload

    return _run_with_session(session, _lookup)


def lookup_word_click(word: str, session: Session | None = None) -> dict:
    """Reader tap: ECDICT/local first; if no Chinese sense, fall back to Youdao and cache."""
    normalized = normalize_word(word)
    if not normalized:
        return _empty_lookup("")

    def _lookup(db: Session) -> dict:
        fast = lookup_word_fast(normalized, session=db)
        has_zh = bool((fast.get("translation") or "").strip() or (fast.get("youdao_translation") or "").strip())
        if has_zh:
            fast["pending_enrichment"] = False
            return fast

        youdao_tr = youdao_lookup_word(normalized)
        if not youdao_tr:
            fast["pending_enrichment"] = False
            return fast

        fast["translation"] = youdao_tr
        fast["youdao_translation"] = youdao_tr
        if fast.get("lookup_source") in (None, "", "miss"):
            fast["lookup_source"] = "youdao"
        fast["pending_enrichment"] = False
        _save_cache(db, fast, source_name="online-cache")
        return fast

    return _run_with_session(session, _lookup)


def lookup_word(word: str, session: Session | None = None) -> dict:
    return lookup_word_enrich(word, session=session)


@lru_cache(maxsize=512)
def _lookup_online(word: str) -> Optional[dict]:
    return _fetch_dictionaryapi(word, timeout=8)


def _lookup_online_fast(word: str) -> Optional[dict]:
    """有道已有释义时，短超时补充英文释义，避免拖慢查词"""
    return _fetch_dictionaryapi(word, timeout=2)


def _lookup_online_bundle(word: str) -> Optional[dict]:
    youdao_tr = youdao_lookup_word(word)
    result = _lookup_online(word) if not youdao_tr else _lookup_online_fast(word)
    if result:
        result["youdao_translation"] = youdao_tr
        result["translation"] = youdao_tr or result.get("definition")
        result["lemma"] = normalize_word(result.get("word") or word) or word
        result["lookup_source"] = "online-cache"
        return result

    if youdao_tr:
        return {
            "word": word,
            "lemma": word,
            "definition": "",
            "pronunciation": None,
            "part_of_speech": None,
            "example": None,
            "translation": youdao_tr,
            "youdao_translation": youdao_tr,
            "lookup_source": "online-cache",
        }
    return None


def _fetch_dictionaryapi(word: str, timeout: float) -> Optional[dict]:
    try:
        resp = httpx.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}",
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        entry = data[0]
        meanings = entry.get("meanings", [])
        if not meanings:
            return None
        meaning = meanings[0]
        definitions = meaning.get("definitions", [])
        definition = definitions[0].get("definition", "") if definitions else ""
        example = definitions[0].get("example") if definitions else None

        phonetic = None
        for p in entry.get("phonetics", []):
            if p.get("text"):
                phonetic = p["text"]
                break
        if not phonetic and entry.get("phonetic"):
            phonetic = entry["phonetic"]

        return {
            "word": word,
            "definition": definition,
            "pronunciation": phonetic,
            "part_of_speech": meaning.get("partOfSpeech"),
            "example": example,
        }
    except Exception as e:
        logger.debug("online lookup failed for %s: %s", word, e)
        return None
