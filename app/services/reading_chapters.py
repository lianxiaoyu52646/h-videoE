from __future__ import annotations

from typing import Protocol

from sqlmodel import Session, select

from app import models
from app.services.reading_limits import MAX_CHAPTER_BLOCKS, MIN_CHAPTER_BLOCKS


class BlockMeta(Protocol):
    order_index: int
    section_title: str | None


def derive_chapter_specs(blocks: list[BlockMeta]) -> list[dict]:
    if not blocks:
        return []

    has_titles = any((b.section_title or "").strip() for b in blocks)
    if not has_titles:
        return _split_large_specs(
            [
                {
                    "title": "全文",
                    "start_block": blocks[0].order_index,
                    "end_block": blocks[-1].order_index,
                    "block_count": len(blocks),
                }
            ]
        )

    chapters: list[dict] = []
    for block in blocks:
        raw_title = (block.section_title or "").strip()
        if not chapters:
            title = raw_title or "开篇"
            chapters.append(
                {
                    "title": title,
                    "start_block": block.order_index,
                    "end_block": block.order_index,
                    "block_count": 1,
                }
            )
            continue

        last = chapters[-1]
        if raw_title and raw_title != last["title"]:
            chapters.append(
                {
                    "title": raw_title,
                    "start_block": block.order_index,
                    "end_block": block.order_index,
                    "block_count": 1,
                }
            )
        else:
            last["end_block"] = block.order_index
            last["block_count"] = last["end_block"] - last["start_block"] + 1

    return _balance_specs(chapters)


def _balance_specs(specs: list[dict]) -> list[dict]:
    if len(specs) <= 1:
        return _split_large_specs(specs)

    merged: list[dict] = [dict(specs[0])]
    for spec in specs[1:]:
        prev = merged[-1]
        same_title = spec["title"] == prev["title"]
        combined = prev["block_count"] + spec["block_count"]
        should_merge = (
            combined <= MAX_CHAPTER_BLOCKS
            and same_title
            and prev["block_count"] < MIN_CHAPTER_BLOCKS
        )
        if should_merge:
            prev["end_block"] = spec["end_block"]
            prev["block_count"] = combined
        else:
            merged.append(dict(spec))

    return _split_large_specs(merged)


def _split_large_specs(specs: list[dict]) -> list[dict]:
    final: list[dict] = []
    for spec in specs:
        if spec["block_count"] <= MAX_CHAPTER_BLOCKS:
            final.append(spec)
            continue
        start = spec["start_block"]
        end = spec["end_block"]
        title = spec["title"]
        chunk_starts = list(range(start, end + 1, MAX_CHAPTER_BLOCKS))
        parts = len(chunk_starts)
        for idx, chunk_start in enumerate(chunk_starts):
            chunk_end = min(end, chunk_start + MAX_CHAPTER_BLOCKS - 1)
            part_title = f"{title} ({idx + 1}/{parts})" if parts > 1 else title
            final.append(
                {
                    "title": part_title,
                    "start_block": chunk_start,
                    "end_block": chunk_end,
                    "block_count": chunk_end - chunk_start + 1,
                }
            )
    return final or specs


def chapter_for_block(chapters: list[models.ReadingChapter], block_index: int) -> int:
    if not chapters:
        return 0
    for chapter in chapters:
        if chapter.start_block <= block_index <= chapter.end_block:
            return chapter.chapter_index
    if block_index < chapters[0].start_block:
        return 0
    return chapters[-1].chapter_index
