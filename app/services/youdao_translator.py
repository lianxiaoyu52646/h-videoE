"""
国内有道免费翻译 — 基于 dict.youdao.com（个人可用，无需 API Key）

- 段落/句子：jsonapi_s（自动语种，英↔中）
- 单词释义：suggest
"""
import logging
import os
import re
import threading
import time
from functools import lru_cache
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_JSONAPI_URL = "https://dict.youdao.com/jsonapi_s"
_SUGGEST_URL = "https://dict.youdao.com/suggest"

_MAX_CHARS = int(os.getenv("YOUDAO_MAX_CHARS", "800"))
_RATE_INTERVAL = float(os.getenv("YOUDAO_RATE_INTERVAL", "0.35"))
_MAX_RETRIES = int(os.getenv("YOUDAO_MAX_RETRIES", "3"))

_rate_lock = threading.Lock()
_last_request_at = 0.0

_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://dict.youdao.com/",
}


def _rate_wait():
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        gap = _RATE_INTERVAL - (now - _last_request_at)
        if gap > 0:
            time.sleep(gap)
        _last_request_at = time.monotonic()


def _is_chinese(text: str) -> bool:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _lang_param(source: str, text: str) -> Optional[str]:
    """jsonapi_s：英文显式传 le=en，中文/auto 省略 le 让接口自动检测"""
    src = (source or "auto").lower()
    if src in ("en", "eng", "english"):
        return "en"
    if src.startswith("zh") or _is_chinese(text):
        return None
    return None


def _split_long_text(text: str, max_chars: int = _MAX_CHARS) -> List[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    chunks: List[str] = []
    buf = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = f"{buf} {part}".strip() if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(part) <= max_chars:
            buf = part
        else:
            for i in range(0, len(part), max_chars):
                chunks.append(part[i : i + max_chars].strip())
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [text[:max_chars]]


def _normalize_text(text: str) -> str:
    text = (text or "").replace("\u00a0", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def _translate_with_retries(text: str, source: str) -> str:
    result = ""
    for attempt in range(_MAX_RETRIES):
        try:
            _rate_wait()
            result = _request_jsonapi(text, source=source)
            if result:
                break
        except Exception as e:
            logger.warning(
                "youdao translate attempt %d failed: %s", attempt + 1, e
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(0.8 * (attempt + 1))
    return result.strip()


def _translate_aggressive(text: str, source: str) -> str:
    result = _translate_with_retries(text, source)
    if result or len(text) <= 120:
        return result

    fallback_max = max(120, min(240, _MAX_CHARS // 2))
    fallback_chunks = _split_long_text(text, max_chars=fallback_max)
    if len(fallback_chunks) <= 1 and len(text) > fallback_max:
        fallback_chunks = [text[i : i + fallback_max].strip() for i in range(0, len(text), fallback_max)]

    parts: List[str] = []
    for chunk in fallback_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        chunk_result = _translate_with_retries(chunk, source)
        if chunk_result:
            parts.append(chunk_result)
    return " ".join(parts).strip()


def _extract_ec_translation(data: dict) -> str:
    """短句/词组时 jsonapi_s 常无 fanyi，释义在 ec.word[].trs 中"""
    words = (data.get("ec") or {}).get("word") or []
    if not words:
        return ""

    parts: List[str] = []
    for entry in words[:1]:
        for tr_group in entry.get("trs") or []:
            for tr_item in tr_group.get("tr") or []:
                l_obj = tr_item.get("l") or {}
                items = l_obj.get("i")
                if isinstance(items, list):
                    for item in items:
                        text = (item or "").strip()
                        if text:
                            parts.append(text)
                elif isinstance(items, str):
                    text = items.strip()
                    if text:
                        parts.append(text)

    seen: set[str] = set()
    unique: List[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            unique.append(part)
    return "；".join(unique[:3]).strip()


def _parse_jsonapi_response(data: dict) -> str:
    fanyi = (data.get("fanyi") or {}).get("tran") or ""
    result = fanyi.strip()
    if result:
        return result
    return _extract_ec_translation(data)


def _request_jsonapi(text: str, source: str = "auto", *, omit_le: bool = False) -> str:
    params = {"q": text, "t": str(int(time.time() * 1000))}
    if not omit_le:
        lang = _lang_param(source, text)
        if lang:
            params["le"] = lang

    with httpx.Client(timeout=12, follow_redirects=True) as client:
        resp = client.get(_JSONAPI_URL, params=params, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    result = _parse_jsonapi_response(data)
    if result:
        return result

    if not omit_le:
        return _request_jsonapi(text, source=source, omit_le=True)

    logger.debug("youdao jsonapi empty for %r, keys=%s", text[:60], list(data.keys()))
    return ""


def translate_text(text: str, source: str = "auto", target: str = "auto") -> str:
    """翻译单段文本（含超长自动分句）"""
    text = _normalize_text(text)
    if not text:
        return ""

    chunks = _split_long_text(text)
    translated: List[str] = []
    for chunk in chunks:
        result = _translate_aggressive(_normalize_text(chunk), source=source)
        translated.append(result)
    return "".join(translated) if len(translated) == 1 else " ".join(translated)


def translate_batch(texts: List[str], source: str = "auto", target: str = "auto") -> List[str]:
    return [translate_text(t, source, target) for t in texts]


@lru_cache(maxsize=512)
def lookup_word(word: str) -> Optional[str]:
    """单词有道释义（suggest 接口）"""
    word = re.sub(r"[^A-Za-z'-]", "", word).strip().lower()
    if not word:
        return None
    try:
        _rate_wait()
        resp = httpx.get(
            _SUGGEST_URL,
            params={"type": "2", "doctype": "json", "q": word},
            headers=_HEADERS,
            timeout=10,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        entries = resp.json().get("data", {}).get("entries", [])
        if not entries:
            return None
        for entry in entries:
            if entry.get("entry", "").lower() == word.lower():
                return entry.get("explain") or None
        return entries[0].get("explain") or None
    except Exception as e:
        logger.debug("youdao suggest failed for %s: %s", word, e)
        return None
