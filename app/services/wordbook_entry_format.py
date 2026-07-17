from __future__ import annotations

import re

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def normalize_catalog_entry(entry: dict) -> dict:
    translation = (entry.get("translation") or "").strip()
    definition = (entry.get("definition") or "").strip()
    if translation and definition and translation == definition:
        if has_cjk(translation):
            definition = ""
    if translation and not has_cjk(translation) and not definition:
        definition = translation
        translation = ""
    elif translation and not has_cjk(translation) and has_cjk(definition):
        translation, definition = definition, translation
    pronunciation = (entry.get("pronunciation") or "").strip()
    normalized = dict(entry)
    normalized["translation"] = translation or None
    normalized["definition"] = definition
    normalized["pronunciation"] = pronunciation or None
    normalized["example"] = (entry.get("example") or "").strip() or None
    normalized["part_of_speech"] = (entry.get("part_of_speech") or "").strip() or None
    return normalized
