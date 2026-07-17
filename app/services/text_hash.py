"""文本哈希 — 译文缓存键"""
import hashlib


def text_hash(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
