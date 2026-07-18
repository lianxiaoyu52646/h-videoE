"""阅读文档后台翻译 — 按需章节翻译 + 全书翻译 + SSE 推送"""
import asyncio
import logging
import re
from typing import Callable, Optional

from sqlmodel import Session

from app import crud
from app import database
from app.models import Job, ReadingBlock, ReadingDocument
from app.services import reading_cache, translator
from app.services import translate_progress

logger = logging.getLogger(__name__)

engine = database.engine

MIN_TRANSLATE_RATIO = 0.8
BATCH_SIZE = 10

_running_tasks: dict[int, asyncio.Task] = {}
_generations: dict[int, int] = {}
_chapter_queues: dict[int, asyncio.Queue] = {}
_queue_workers: dict[int, asyncio.Task] = {}
_queued_chapters: dict[int, set[int]] = {}
_sse_publish: Optional[Callable[[int, str, dict], None]] = None


def set_sse_publisher(fn: Callable[[int, str, dict], None]):
    global _sse_publish
    _sse_publish = fn


def is_translating(doc_id: int) -> bool:
    task = _running_tasks.get(doc_id)
    if task is not None and not task.done():
        return True
    worker = _queue_workers.get(doc_id)
    return worker is not None and not worker.done()


def _emit(doc_id: int, event: str, data: dict):
    if _sse_publish:
        _sse_publish(doc_id, event, data)


def _update_doc_job(
    doc_id: int,
    *,
    job_id: int | None = None,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
):
    with Session(database.engine) as db:
        doc = db.get(ReadingDocument, doc_id)
        if not doc:
            return
        if status is not None:
            doc.translate_status = status
        if progress is not None:
            doc.translate_progress = max(0, min(100, progress))
        if message is not None:
            doc.status_message = message
        target_job_id = job_id or doc.active_job_id
        if target_job_id:
            job = db.get(Job, target_job_id)
            if job:
                if status is not None:
                    job.status = status
                    if status not in {"done", "failed"} and job.started_at is None:
                        job.started_at = crud._utc_now()
                    if status in {"done", "failed"}:
                        job.finished_at = crud._utc_now()
                if progress is not None:
                    job.progress = max(0, min(100, progress))
                if message is not None:
                    job.message = message
                db.add(job)
        db.add(doc)
        db.commit()


async def _cancel_doc_task(doc_id: int):
    task = _running_tasks.pop(doc_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _stop_chapter_worker(doc_id: int):
    queued = _queued_chapters.pop(doc_id, None)
    if queued is not None:
        queued.clear()
    queue = _chapter_queues.get(doc_id)
    if queue is not None:
        while not queue.empty():
            try:
                queue.get_nowait()
                queue.task_done()
            except asyncio.QueueEmpty:
                break
    worker = _queue_workers.pop(doc_id, None)
    if worker and not worker.done():
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


_main_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _main_loop
    _main_loop = loop


def _schedule(coro):
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(coro)
    except RuntimeError:
        if _main_loop is not None and _main_loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, _main_loop)
        import threading

        def _run():
            asyncio.run(coro)

        threading.Thread(target=_run, daemon=True).start()
        return None


def start_translation(
    doc_id: int,
    force: bool = False,
    job_id: int | None = None,
    *,
    replace: bool = False,
):
    """全书翻译；replace=True 时取消进行中的任务但不清空已有译文"""
    _schedule(translate_document(doc_id, force=force, job_id=job_id, replace=replace))


def start_untranslated_translation(doc_id: int, job_id: int | None = None):
    """补译全书未翻译段落（保留已持久化译文）"""
    start_translation(doc_id, force=False, job_id=job_id, replace=True)


def start_chapter_translation(
    doc_id: int,
    chapter_index: int,
    *,
    prefetch_next: bool = False,
    job_id: int | None = None,
):
    """按需翻译指定章节（懒加载）"""
    _schedule(_enqueue_chapter(doc_id, chapter_index, prefetch_next, job_id))


async def run_chapter_job(
    doc_id: int,
    chapter_index: int,
    *,
    prefetch_next: bool = False,
    job_id: int | None = None,
):
    """供 worker 直接执行章节翻译"""
    await _enqueue_chapter(doc_id, chapter_index, prefetch_next, job_id)
    worker = _queue_workers.get(doc_id)
    if worker is not None:
        await worker


async def _enqueue_chapter(
    doc_id: int,
    chapter_index: int,
    prefetch_next: bool,
    job_id: int | None,
):
    queued = _queued_chapters.setdefault(doc_id, set())
    if chapter_index in queued:
        return
    queued.add(chapter_index)
    queue = _chapter_queues.setdefault(doc_id, asyncio.Queue())
    await queue.put((chapter_index, prefetch_next, job_id))
    await _ensure_chapter_worker(doc_id)


async def _ensure_chapter_worker(doc_id: int):
    worker = _queue_workers.get(doc_id)
    if worker is not None and not worker.done():
        return
    _queue_workers[doc_id] = asyncio.create_task(_chapter_queue_worker(doc_id))


async def _chapter_queue_worker(doc_id: int):
    queue = _chapter_queues.setdefault(doc_id, asyncio.Queue())
    try:
        while True:
            try:
                chapter_index, prefetch_next, job_id = await asyncio.wait_for(
                    queue.get(), timeout=45.0
                )
            except asyncio.TimeoutError:
                break
            _queued_chapters.get(doc_id, set()).discard(chapter_index)
            try:
                next_chapter = await _translate_chapter_impl(
                    doc_id, chapter_index, job_id=job_id
                )
                if prefetch_next and next_chapter is not None:
                    await _enqueue_chapter(doc_id, next_chapter, True, None)
            finally:
                queue.task_done()
    finally:
        _queue_workers.pop(doc_id, None)
        _queued_chapters.pop(doc_id, None)


async def translate_document(
    doc_id: int,
    force: bool = False,
    job_id: int | None = None,
    *,
    replace: bool = False,
):
    if force or replace:
        _generations[doc_id] = _generations.get(doc_id, 0) + 1
        await _cancel_doc_task(doc_id)
        await _stop_chapter_worker(doc_id)
        if force:
            reading_cache.invalidate_doc(doc_id)
    elif _running_tasks.get(doc_id) is not None and not _running_tasks[doc_id].done():
        return

    gen = _generations.get(doc_id, 0) + 1
    _generations[doc_id] = gen

    task = asyncio.create_task(_translate_full_impl(doc_id, gen, force, job_id))
    _running_tasks[doc_id] = task
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        if _running_tasks.get(doc_id) is task:
            _running_tasks.pop(doc_id, None)


def _stale(doc_id: int, gen: int) -> bool:
    return _generations.get(doc_id, 0) != gen


def _normalize_source_text(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split())


def _is_meaningful_text(text: str) -> bool:
    normalized = _normalize_source_text(text)
    if not normalized:
        return False
    if re.fullmatch(r"[*=_~\-.•·\s]+", normalized):
        return False
    return len(re.findall(r"[A-Za-z]", normalized)) >= 3


def _get_blocks_range(doc_id: int, start_block: int, end_block: int) -> list[ReadingBlock]:
    with Session(database.engine) as db:
        return crud.get_reading_blocks_in_range(db, doc_id, start_block, end_block)


def _get_blocks(doc_id: int) -> list[ReadingBlock]:
    with Session(database.engine) as db:
        return reading_cache.get_all_blocks(db, doc_id)


def _sync_doc_progress(
    doc_id: int,
    *,
    status: str | None = None,
    message: str | None = None,
    reconcile: bool = False,
):
    with Session(database.engine) as db:
        doc = db.get(ReadingDocument, doc_id)
        if not doc:
            return 0, 0
        if reconcile:
            translated = crud.sync_translated_blocks(db, doc_id)
            db.commit()
            db.refresh(doc)
        else:
            translated = int(doc.translated_blocks or 0)
        total = doc.block_count or 0
        translate_progress.mark_progress(doc_id, translated, total)
        if status is not None:
            doc.translate_status = status
        if message is not None:
            doc.status_message = message
        elif doc.translate_status == "translating":
            doc.status_message = translate_progress.format_progress_message(
                translated, total, doc_id=doc_id
            )
        if total > 0 and translated >= total:
            doc.translate_status = "done"
            doc.translate_progress = 100
            if not message:
                doc.status_message = "翻译完成"
        db.add(doc)
        db.commit()
        return translated, total


async def _translate_batch(
    db: Session,
    need: list[ReadingBlock],
    *,
    skip_cache: bool = False,
) -> list[str]:
    results: list[str] = []
    api_texts: list[str] = []
    api_map: list[int] = []

    for i, block in enumerate(need):
        source_text = _normalize_source_text(block.text)
        if not _is_meaningful_text(source_text):
            results.append("")
            continue
        cached = None if skip_cache else crud.get_translation_from_cache(
            db, block.text, record_hit=False
        )
        if cached:
            results.append(cached)
        else:
            results.append("")
            api_texts.append(source_text)
            api_map.append(i)

    if api_texts:
        api_results = await translator.translate_reading_paragraphs(api_texts)
        for pos, tr in zip(api_map, api_results):
            results[pos] = (tr or "").strip()

    return results


async def _process_batch(
    doc_id: int,
    gen: int,
    need: list[ReadingBlock],
    *,
    force: bool,
    job_id: int | None,
) -> bool:
    """翻译一批段落并写库，返回是否因 stale 中断"""
    if not need or _stale(doc_id, gen):
        return False

    with Session(database.engine) as db:
        translated = await _translate_batch(db, need, skip_cache=force)

    if _stale(doc_id, gen):
        return False

    with Session(database.engine) as db:
        newly_translated = 0
        for j, block in enumerate(need):
            db_block = db.get(ReadingBlock, block.id)
            if db_block and j < len(translated):
                tr = (translated[j] or "").strip()
                had_translation = bool((db_block.translation or "").strip())
                db_block.translation = tr or None
                db.add(db_block)
                if tr and not had_translation:
                    newly_translated += 1
                if tr:
                    crud.save_translation_cache(db, block.text, tr)
                reading_cache.patch_block_translation(
                    doc_id, db_block.order_index, tr or None
                )
                _emit(doc_id, "translated", {
                    "block_id": db_block.id,
                    "order_index": db_block.order_index,
                    "translation": tr,
                })
        if newly_translated:
            crud.increment_translated_blocks(db, doc_id, newly_translated)
        db.commit()
    return True


async def _retry_untranslated_in_range(
    doc_id: int,
    gen: int,
    start_block: int,
    end_block: int,
    job_id: int | None,
    *,
    skip_cache: bool = False,
) -> None:
    blocks = [
        block
        for block in _get_blocks_range(doc_id, start_block, end_block)
        if _is_meaningful_text(block.text) and not (block.translation or "").strip()
    ]
    if not blocks:
        return

    for block in blocks:
        if _stale(doc_id, gen):
            return
        source_text = _normalize_source_text(block.text)
        tr = ""
        if not skip_cache:
            with Session(database.engine) as db:
                cached = crud.get_translation_from_cache(db, block.text, record_hit=False)
            tr = (cached or "").strip()
        if not tr:
            tr = (
                await asyncio.to_thread(
                    translator.translate_text,
                    source_text,
                    "en",
                    "zh-CN",
                )
            ).strip()
        if not tr:
            continue
        with Session(database.engine) as db:
            db_block = db.get(ReadingBlock, block.id)
            if db_block:
                had_translation = bool((db_block.translation or "").strip())
                db_block.translation = tr
                db.add(db_block)
                crud.save_translation_cache(db, block.text, tr)
                if not had_translation:
                    crud.increment_translated_blocks(db, doc_id, 1)
                db.commit()
                reading_cache.patch_block_translation(doc_id, db_block.order_index, tr)
                _emit(doc_id, "translated", {
                    "block_id": db_block.id,
                    "order_index": db_block.order_index,
                    "translation": tr,
                })


def _range_success(blocks: list[ReadingBlock]) -> tuple[int, int, float]:
    text_blocks = [b for b in blocks if _is_meaningful_text(b.text)]
    nonempty = sum(1 for b in text_blocks if (b.translation or "").strip())
    ratio = nonempty / max(len(text_blocks), 1)
    return len(text_blocks), nonempty, ratio


async def _translate_range_impl(
    doc_id: int,
    gen: int,
    start_block: int,
    end_block: int,
    *,
    force: bool = False,
    skip_cache: bool = False,
    job_id: int | None = None,
) -> tuple[int, int, float]:
    """翻译 block 范围，返回 (meaningful, translated, ratio)"""
    with Session(database.engine) as db:
        if not skip_cache:
            applied = crud.apply_cached_translations_in_range(
                db, doc_id, start_block, end_block
            )
            if applied:
                reading_cache.invalidate_doc(doc_id)

    blocks = _get_blocks_range(doc_id, start_block, end_block)
    total = len(blocks)
    done = 0

    for i in range(0, total, BATCH_SIZE):
        if _stale(doc_id, gen):
            break
        batch = blocks[i : i + BATCH_SIZE]
        need = [
            b for b in batch
            if (force or not (b.translation or "").strip()) and b.text.strip()
        ]
        if need:
            await _process_batch(doc_id, gen, need, force=skip_cache or force, job_id=job_id)
        done += len(batch)
        translated, doc_total = _sync_doc_progress(doc_id)
        progress_msg = translate_progress.format_progress_message(
            translated, doc_total, doc_id=doc_id, prefix="补译中" if not force else "翻译中"
        )
        _update_doc_job(
            doc_id,
            job_id=job_id,
            status="translating",
            progress=min(99, int(translated / max(doc_total, 1) * 100)),
            message=progress_msg,
        )
        _emit(doc_id, "progress", {
            "translated_blocks": translated,
            "translate_progress": min(99, int(translated / max(doc_total, 1) * 100)),
            "status_message": progress_msg,
        })

    if not _stale(doc_id, gen):
        await _retry_untranslated_in_range(
            doc_id, gen, start_block, end_block, job_id, skip_cache=skip_cache or force
        )

    blocks = _get_blocks_range(doc_id, start_block, end_block)
    return _range_success(blocks)


async def _translate_chapter_impl(
    doc_id: int,
    chapter_index: int,
    *,
    job_id: int | None = None,
) -> int | None:
    """翻译单章，返回建议预取的下一章 index（若有）"""
    with Session(database.engine) as db:
        chapter = crud.get_reading_chapter(db, doc_id, chapter_index)
        if not chapter:
            return None
        doc = db.get(ReadingDocument, doc_id)
        if not doc:
            return None
        chapters = crud.list_reading_chapters(db, doc_id)

    gen = _generations.get(doc_id, 0)
    _update_doc_job(
        doc_id,
        job_id=job_id,
        status="translating",
        message=f"正在翻译：{chapter.title or f'第 {chapter_index + 1} 章'}",
    )
    _emit(doc_id, "status", {
        "translate_status": "translating",
        "chapter_index": chapter_index,
        "status_message": f"正在翻译：{chapter.title or f'第 {chapter_index + 1} 章'}",
    })

    meaningful, nonempty, ratio = await _translate_range_impl(
        doc_id,
        gen,
        chapter.start_block,
        chapter.end_block,
        job_id=job_id,
    )

    translated, doc_total = _sync_doc_progress(doc_id)
    all_done = doc_total > 0 and translated >= doc_total

    if all_done:
        status = "done"
        message = "翻译完成"
        event = "done"
    elif ratio >= MIN_TRANSLATE_RATIO or nonempty > 0:
        status = "ready"
        if meaningful > nonempty:
            message = (
                f"{chapter.title or f'第 {chapter_index + 1} 章'}已可阅读"
                f"（{nonempty}/{meaningful} 段已译）"
            )
        else:
            message = f"{chapter.title or f'第 {chapter_index + 1} 章'}翻译完成"
        event = "chapter_done"
    else:
        status = "ready"
        message = (
            f"{chapter.title or f'第 {chapter_index + 1} 章'}部分段落未译出，阅读时可重试"
        )
        event = "chapter_done"

    _sync_doc_progress(
        doc_id,
        status=status,
        message=message if not all_done else "翻译完成",
        reconcile=True,
    )
    _update_doc_job(
        doc_id,
        job_id=job_id,
        status="done" if all_done else status,
        progress=100 if all_done else min(99, int(translated / max(doc_total, 1) * 100)),
        message=message,
    )
    _emit(doc_id, event, {
        "translate_status": status,
        "chapter_index": chapter_index,
        "status_message": message,
        "translated_blocks": translated,
        "translate_progress": min(100, int(translated / max(doc_total, 1) * 100)),
    })

    if chapter_index + 1 < len(chapters):
        return chapter_index + 1
    return None


async def _translate_full_impl(doc_id: int, gen: int, force: bool, job_id: int | None):
    try:
        with Session(database.engine) as db:
            doc = db.get(ReadingDocument, doc_id)
            if not doc or _stale(doc_id, gen):
                return
            if not force:
                applied = crud.apply_cached_translations(db, doc_id)
                if applied:
                    reading_cache.invalidate_doc(doc_id)
            doc = db.get(ReadingDocument, doc_id)
            if not doc or _stale(doc_id, gen):
                return
            doc.translate_status = "translating"
            doc.status_message = "全书翻译进行中..." if force else "补译未翻译段落..."
            if force:
                doc.translated_blocks = 0
                doc.translate_progress = 0
            db.add(doc)
            db.commit()

        _update_doc_job(
            doc_id, job_id=job_id, status="translating", progress=5, message="全书翻译进行中..."
        )

        blocks = _get_blocks(doc_id)
        if not blocks:
            _sync_doc_progress(doc_id, status="done", message="翻译完成", reconcile=True)
            _emit(doc_id, "done", {"translate_status": "done"})
            return

        start = blocks[0].order_index
        end = blocks[-1].order_index
        meaningful, nonempty, ratio = await _translate_range_impl(
            doc_id, gen, start, end, force=force, skip_cache=force, job_id=job_id
        )

        if _stale(doc_id, gen):
            return

        if ratio >= MIN_TRANSLATE_RATIO:
            status = "done"
            if nonempty < meaningful:
                message = f"翻译完成（{meaningful - nonempty} 段未译出，可重试）"
            else:
                message = "翻译完成"
            event = "done"
        else:
            status = "failed"
            message = translate_progress.format_failure_message(
                nonempty, meaningful, rate_limited=(nonempty > 0 and ratio < 0.35)
            )
            event = "error"

        _sync_doc_progress(doc_id, status=status, message=message, reconcile=True)
        _update_doc_job(
            doc_id,
            job_id=job_id,
            status="done" if event == "done" else "failed",
            progress=100,
            message=message,
        )
        reading_cache.invalidate_doc(doc_id)
        with Session(database.engine) as db:
            reading_cache.warm_doc(db, doc_id, first_pages=3)
        _emit(doc_id, event, {
            "translate_status": status,
            "status_message": message,
            "message": message,
        })

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("translate failed doc %s", doc_id)
        if _stale(doc_id, gen):
            return
        _sync_doc_progress(doc_id, status="failed", message=str(e), reconcile=True)
        _update_doc_job(doc_id, job_id=job_id, status="failed", progress=100, message=str(e))
        _emit(doc_id, "error", {"message": str(e), "translate_status": "failed"})


def resume_pending_translations():
    """服务启动时：仅恢复全书翻译中的任务，懒加载书保持 ready"""
    with Session(database.engine) as db:
        docs = crud.list_incomplete_readings(db)

    for doc in docs:
        if doc.translate_status != "translating":
            with Session(database.engine) as db:
                translated = crud.count_translated_blocks(db, doc.id)
                total = doc.block_count or 0
                d = db.get(ReadingDocument, doc.id)
                if not d:
                    continue
                if total > 0 and translated >= total:
                    d.translate_status = "done"
                    d.translate_progress = 100
                    d.status_message = "翻译完成"
                elif doc.translate_status == "pending":
                    d.translate_status = "ready"
                    d.status_message = "可以开始阅读（打开章节后自动翻译）"
                db.add(d)
                db.commit()
            continue

        with Session(database.engine) as db:
            job = db.get(Job, doc.active_job_id) if doc.active_job_id else None
        payload = (job.payload_json or {}) if job else {}
        if payload.get("mode") == "chapter":
            chapter_index = payload.get("chapter_index", 0)
            start_chapter_translation(
                doc.id,
                chapter_index,
                prefetch_next=payload.get("prefetch_next", False),
                job_id=doc.active_job_id,
            )
        else:
            start_translation(doc.id, job_id=doc.active_job_id)
