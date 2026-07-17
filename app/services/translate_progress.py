"""翻译进度与 ETA 估算"""
from __future__ import annotations

import time
from typing import Optional

from app.services.reading_limits import DEFAULT_SEC_PER_BLOCK

_doc_stats: dict[int, dict] = {}


def mark_progress(doc_id: int, translated: int, total: int) -> None:
    now = time.monotonic()
    stats = _doc_stats.setdefault(doc_id, {"started": now, "last_at": now, "last_count": 0})
    stats["last_at"] = now
    stats["last_count"] = translated
    stats["total"] = total


def format_progress_message(
    translated: int,
    total: int,
    *,
    doc_id: Optional[int] = None,
    prefix: str = "翻译中",
) -> str:
    total = max(total, 1)
    translated = max(0, min(translated, total))
    pct = int(translated / total * 100)
    remaining = total - translated

    eta_sec = _estimate_seconds(doc_id, translated, remaining)
    base = f"{prefix}：已译 {translated}/{total} 段（{pct}%）"
    if remaining <= 0:
        return f"翻译完成：{translated}/{total} 段"
    if eta_sec is None:
        return base
    return f"{base} · 约还需 {_format_duration(eta_sec)}"


def format_failure_message(translated: int, total: int, *, rate_limited: bool = False) -> str:
    if rate_limited:
        return (
            f"翻译接口繁忙：已译 {translated}/{total} 段。"
            "请稍等几分钟后点「补译未译段落」，已译内容不会丢失。"
        )
    if total > 0 and translated / total >= 0.5:
        return (
            f"部分段落暂未译出（{translated}/{total} 段已成功）。"
            "可先读英文，稍后再点「补译未译段落」。"
        )
    return (
        f"翻译未完成（仅 {translated}/{total} 段成功）。"
        "请检查网络或稍后再试；短句/标题有时需多次补译。"
    )


def _estimate_seconds(doc_id: Optional[int], translated: int, remaining: int) -> Optional[float]:
    if remaining <= 0:
        return 0.0
    rate = None
    if doc_id is not None:
        stats = _doc_stats.get(doc_id)
        if stats:
            elapsed = max(0.001, stats["last_at"] - stats["started"])
            delta = max(0, translated - stats.get("boot_count", 0))
            if delta >= 3 and elapsed > 0:
                rate = delta / elapsed
    sec_per = 1.0 / rate if rate and rate > 0 else DEFAULT_SEC_PER_BLOCK
    return remaining * sec_per


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} 秒"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    hours = minutes // 60
    rem = minutes % 60
    return f"{hours} 小时 {rem} 分钟" if rem else f"{hours} 小时"
