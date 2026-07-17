from __future__ import annotations

import difflib
import json
import re
from bisect import bisect_left
from collections import OrderedDict
from pathlib import Path
from typing import Iterable


_WORD_RE = re.compile(r"[^A-Za-z'-]")
_IRREGULAR_LEMMAS = {
    "am": "be",
    "are": "be",
    "been": "be",
    "being": "be",
    "better": "good",
    "best": "good",
    "bought": "buy",
    "brought": "bring",
    "came": "come",
    "children": "child",
    "did": "do",
    "does": "do",
    "doing": "do",
    "done": "do",
    "driven": "drive",
    "drove": "drive",
    "feet": "foot",
    "fell": "fall",
    "felt": "feel",
    "found": "find",
    "gave": "give",
    "gone": "go",
    "got": "get",
    "had": "have",
    "has": "have",
    "having": "have",
    "held": "hold",
    "kept": "keep",
    "knew": "know",
    "known": "know",
    "left": "leave",
    "made": "make",
    "men": "man",
    "met": "meet",
    "ran": "run",
    "said": "say",
    "saw": "see",
    "seen": "see",
    "sent": "send",
    "spoke": "speak",
    "spoken": "speak",
    "taught": "teach",
    "thought": "think",
    "took": "take",
    "went": "go",
    "were": "be",
    "women": "woman",
    "worse": "bad",
    "worst": "bad",
    "written": "write",
    "wrote": "write",
}


def normalize_word(value: str) -> str:
    return _WORD_RE.sub("", value or "").strip().lower()


def _normalize_word_list(value: object) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    normalized_items: list[str] = []
    for item in items:
        normalized = normalize_word(str(item))
        if normalized and normalized not in normalized_items:
            normalized_items.append(normalized)
    return normalized_items


def _merge_unique_words(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group or []:
            if item and item not in merged:
                merged.append(item)
    return merged


def candidate_words(value: str) -> list[str]:
    word = normalize_word(value)
    if not word:
        return []

    candidates: list[str] = []

    def add(item: str | None) -> None:
        normalized = normalize_word(item or "")
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add(word)
    add(_IRREGULAR_LEMMAS.get(word))

    if "'" in word:
        left = word.split("'", 1)[0]
        add(left)
        add(_IRREGULAR_LEMMAS.get(left))

    if len(word) > 4 and word.endswith("ies"):
        add(word[:-3] + "y")
    if len(word) > 3 and word.endswith("es"):
        add(word[:-2])
        add(word[:-1])
    if len(word) > 3 and word.endswith("s"):
        add(word[:-1])

    if len(word) > 5 and word.endswith("ing"):
        stem = word[:-3]
        add(stem)
        add(stem + "e")
        if len(stem) > 2 and stem[-1] == stem[-2]:
            add(stem[:-1])

    if len(word) > 4 and word.endswith("ied"):
        add(word[:-3] + "y")
    if len(word) > 4 and word.endswith("ed"):
        stem = word[:-2]
        add(stem)
        add(stem + "e")
        if len(stem) > 2 and stem[-1] == stem[-2]:
            add(stem[:-1])

    if len(word) > 4 and word.endswith("ly"):
        add(word[:-2])
    if len(word) > 4 and word.endswith("er"):
        add(word[:-2])
        add(word[:-1])
    if len(word) > 5 and word.endswith("est"):
        add(word[:-3])
        add(word[:-2])

    return candidates


def _normalize_entry(entry: dict, source_name: str) -> dict | None:
    word = normalize_word(entry.get("word") or entry.get("entry") or "")
    if not word:
        return None
    lemma = normalize_word(entry.get("lemma") or word) or word
    forms = _merge_unique_words(
        _normalize_word_list(entry.get("forms")),
        _normalize_word_list(entry.get("aliases")),
        _normalize_word_list(entry.get("variants")),
    )
    return {
        "word": word,
        "lemma": lemma,
        "definition": (entry.get("definition") or "").strip(),
        "pronunciation": (entry.get("pronunciation") or "").strip() or None,
        "part_of_speech": (entry.get("part_of_speech") or "").strip() or None,
        "example": (entry.get("example") or "").strip() or None,
        "translation": (entry.get("translation") or "").strip() or None,
        "youdao_translation": (entry.get("youdao_translation") or "").strip() or None,
        "source_name": source_name,
        "lookup_source": source_name,
        "forms": [item for item in forms if item != word],
    }


def _entry_rank(entry: dict) -> tuple[int, int]:
    score = 0
    for key in (
        "translation",
        "youdao_translation",
        "definition",
        "pronunciation",
        "part_of_speech",
        "example",
    ):
        if entry.get(key):
            score += 1
    return (score, len(entry.get("forms") or []))


def _merge_pack_entry(existing: dict | None, incoming: dict) -> dict:
    if not existing:
        return dict(incoming)

    merged = dict(existing)
    existing_rank = _entry_rank(existing)
    incoming_rank = _entry_rank(incoming)

    for key in (
        "lemma",
        "definition",
        "pronunciation",
        "part_of_speech",
        "example",
        "translation",
        "youdao_translation",
    ):
        if incoming.get(key):
            merged[key] = incoming[key]

    merged["forms"] = _merge_unique_words(existing.get("forms", []), incoming.get("forms", []))
    if incoming_rank >= existing_rank:
        merged["source_name"] = incoming.get("source_name", merged.get("source_name"))
        merged["lookup_source"] = incoming.get("lookup_source", merged.get("lookup_source"))
    return merged


class DictionaryEngine:
    def __init__(
        self,
        bundled_dir: Path,
        user_dir: Path,
        *,
        cache_size: int = 2048,
    ) -> None:
        self._bundled_dir = Path(bundled_dir)
        self._user_dir = Path(user_dir)
        self._cache_size = max(128, cache_size)
        self._lookup_cache: OrderedDict[str, dict | None] = OrderedDict()
        self._signature: tuple[tuple[str, int, int], ...] = ()
        self._entries_by_word: dict[str, dict] = {}
        self._entries_by_key: dict[str, dict] = {}
        self._sorted_words: list[str] = []
        self._sorted_keys: list[str] = []

    def invalidate(self) -> None:
        self._signature = ()
        self._entries_by_word = {}
        self._entries_by_key = {}
        self._sorted_words = []
        self._sorted_keys = []
        self._lookup_cache.clear()

    def lookup_local(self, value: str) -> dict | None:
        word = normalize_word(value)
        if not word:
            return None
        cached = self._lookup_cache.get(word)
        if cached is not None or word in self._lookup_cache:
            self._lookup_cache.move_to_end(word)
            return dict(cached) if cached else None

        self._load_if_needed()
        result = None
        for candidate in candidate_words(word):
            entry = self._entries_by_key.get(candidate)
            if entry:
                result = dict(entry)
                result["matched_word"] = candidate
                result["lemma_candidates"] = candidate_words(word)
                break

        self._lookup_cache[word] = dict(result) if result else None
        if len(self._lookup_cache) > self._cache_size:
            self._lookup_cache.popitem(last=False)
        return result

    def suggest(self, value: str, limit: int = 8) -> list[str]:
        prefix = normalize_word(value)
        if not prefix:
            return []
        self._load_if_needed()
        if not self._sorted_words:
            return []

        out: list[str] = []
        seen: set[str] = set()

        def add(item: str | None) -> None:
            normalized = normalize_word(item or "")
            if normalized and normalized not in seen:
                seen.add(normalized)
                out.append(normalized)

        for candidate in self._prefix_matches(self._sorted_words, prefix):
            add(candidate)
            if len(out) >= limit:
                return out

        for candidate in self._prefix_matches(self._sorted_keys, prefix):
            entry = self._entries_by_key.get(candidate)
            add(entry.get("word") if entry else candidate)
            if len(out) >= limit:
                return out

        fuzzy_matches = difflib.get_close_matches(prefix, self._sorted_keys, n=limit * 4, cutoff=0.72)
        for candidate in fuzzy_matches:
            entry = self._entries_by_key.get(candidate)
            add(entry.get("word") if entry else candidate)
            if len(out) >= limit:
                break
        return out

    def _prefix_matches(self, sorted_words: list[str], prefix: str) -> list[str]:
        if not sorted_words:
            return []
        idx = bisect_left(sorted_words, prefix)
        matches: list[str] = []
        while idx < len(sorted_words):
            candidate = sorted_words[idx]
            if not candidate.startswith(prefix):
                break
            matches.append(candidate)
            idx += 1
        return matches

    def _load_if_needed(self) -> None:
        files = list(self._iter_pack_files())
        signature = tuple(
            (str(path), int(path.stat().st_mtime_ns), path.stat().st_size)
            for path in files
        )
        if signature == self._signature:
            return

        entries_by_word: dict[str, dict] = {}
        for path in files:
            source_name = path.stem
            for entry in self._read_pack_file(path, source_name):
                entries_by_word[entry["word"]] = _merge_pack_entry(entries_by_word.get(entry["word"]), entry)

        entries_by_key: dict[str, dict] = {}
        for entry in entries_by_word.values():
            lookup_keys = _merge_unique_words([entry["word"]], entry.get("forms", []))
            for key in lookup_keys:
                existing = entries_by_key.get(key)
                if not existing or _entry_rank(entry) >= _entry_rank(existing):
                    entries_by_key[key] = entry

        self._signature = signature
        self._entries_by_word = entries_by_word
        self._entries_by_key = entries_by_key
        self._sorted_words = sorted(entries_by_word)
        self._sorted_keys = sorted(entries_by_key)
        self._lookup_cache.clear()

    def _iter_pack_files(self) -> Iterable[Path]:
        for folder in (self._bundled_dir, self._user_dir):
            if not folder.exists():
                continue
            for path in sorted(folder.glob("*.json")):
                if path.is_file():
                    yield path

    def _read_pack_file(self, path: Path, source_name: str) -> list[dict]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        if isinstance(raw, dict):
            entries = raw.get("entries") or raw.get("items") or []
        else:
            entries = raw

        if not isinstance(entries, list):
            return []

        normalized: list[dict] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            entry = _normalize_entry(item, source_name)
            if entry:
                normalized.append(entry)
        return normalized
