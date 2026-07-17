"""
翻译服务 — 国内有道（个人免费），不依赖外网 API
"""
import asyncio
import logging
from typing import List

from app.services import youdao_translator

logger = logging.getLogger(__name__)


def translate_text(text: str, source="en", target="zh-CN") -> str:
    return youdao_translator.translate_text(text, source=source, target=target)


def translate_batch(texts: List[str], source="en", target="zh-CN") -> List[str]:
    return youdao_translator.translate_batch(texts, source=source, target=target)


async def translate_reading_paragraphs(texts: List[str]) -> List[str]:
    """阅读段落：逐条翻译"""
    if not texts:
        return []
    return await asyncio.to_thread(
        youdao_translator.translate_batch, texts, "en", "zh-CN"
    )


async def translate_subtitles(segments: List[dict]) -> List[dict]:
    """翻译字幕段落，添加 translation 字段"""
    to_translate = []
    for i, seg in enumerate(segments):
        text = seg.get("text", "")
        lang = seg.get("lang", "")
        if seg.get("translation"):
            continue
        if not text:
            seg["translation"] = ""
            continue
        to_translate.append((i, text, lang))

    if not to_translate:
        return segments

    en_texts: List[str] = []
    en_indices: List[int] = []
    zh_texts: List[str] = []
    zh_indices: List[int] = []

    for idx, text, lang in to_translate:
        if "zh" in lang or _is_chinese(text):
            zh_texts.append(text)
            zh_indices.append(idx)
        else:
            en_texts.append(text)
            en_indices.append(idx)

    logger.info("translating via youdao: %d EN, %d ZH", len(en_texts), len(zh_texts))

    if en_texts:
        results = await asyncio.to_thread(
            youdao_translator.translate_batch, en_texts, "en", "zh-CN"
        )
        for i, idx in enumerate(en_indices):
            segments[idx]["translation"] = results[i] if i < len(results) else ""

    if zh_texts:
        results = await asyncio.to_thread(
            youdao_translator.translate_batch, zh_texts, "zh-CN", "en"
        )
        for i, idx in enumerate(zh_indices):
            if i < len(results) and results[i]:
                segments[idx]["translation"] = zh_texts[i]
                segments[idx]["text"] = results[i]
            else:
                segments[idx]["translation"] = ""

    success = sum(1 for seg in segments if seg.get("translation"))
    logger.info("done: %d/%d translated", success, len(to_translate))
    return segments


def _is_chinese(text: str) -> bool:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False
