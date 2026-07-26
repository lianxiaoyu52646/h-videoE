"""Book translation backfill jobs — async, book-by-book, batched, skip done."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from sqlmodel import Session, func, select

from app import crud, database, models
from app.services import book_shared, translator

logger = logging.getLogger(__name__)


def _paragraph_count(session: Session, edition_id: int) -> int:
    return int(
        session.exec(
            select(func.count(models.BookParagraph.id)).where(
                models.BookParagraph.edition_id == edition_id
            )
        ).one()
        or 0
    )

_running = False
_progress: dict[str, Any] = {
    "running": False,
    "job_id": None,
    "current_book_key": None,
    "current_title": None,
    "books_done": 0,
    "books_skipped": 0,
    "books_total": 0,
    "books_finished": 0,
    "percent": 0,
    "translated": 0,
    "failed": 0,
    "message": "",
}


def is_backfill_running() -> bool:
    return _running


def get_backfill_progress() -> dict[str, Any]:
    return dict(_progress)


def _set_progress(**kwargs) -> None:
    _progress.update(kwargs)
    _progress["running"] = _running


def _is_meaningful_text(text: str) -> bool:
    normalized = " ".join((text or "").replace("\u00a0", " ").split())
    if not normalized:
        return False
    if re.fullmatch(r"[*=_~\-.•·\s]+", normalized):
        return False
    return len(re.findall(r"[A-Za-z]", normalized)) >= 3


def _update_job(
    session: Session,
    job_id: int | None,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
) -> None:
    if not job_id:
        return
    job = session.get(models.Job, job_id)
    if not job:
        return
    if status is not None:
        job.status = status
        if status == "running" and job.started_at is None:
            job.started_at = crud._utc_now()
        if status in {"done", "failed"}:
            job.finished_at = crud._utc_now()
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if message is not None:
        job.message = message
    session.add(job)
    session.commit()


async def _translate_edition_batches(
    session: Session,
    edition: models.BookEdition,
    *,
    batch_size: int,
    paragraph_budget: int,
    on_batch=None,
) -> tuple[int, int, int]:
    """Translate one edition in batches. Returns (translated, failed, used_budget)."""
    translated = 0
    failed = 0
    used = 0
    eid = edition.id
    assert eid is not None

    while used < paragraph_budget:
        take = min(batch_size, paragraph_budget - used)
        missing = book_shared.list_missing_paragraphs(
            session, edition_id=eid, limit=take
        )
        if not missing:
            break

        to_api: list[models.BookParagraph] = []
        last_order = edition.translated_blocks or 0
        for para in missing:
            if not _is_meaningful_text(para.en_text):
                book_shared.mark_paragraph_skipped(session, para)
                translated += 1
                used += 1
                last_order = max(last_order, int(para.order_index or 0))
                continue
            to_api.append(para)

        session.commit()

        if to_api:
            texts = [p.en_text for p in to_api]
            zh_list = await asyncio.to_thread(
                translator.translate_batch, texts, "en", "zh-CN"
            )
            orders: list[int] = []
            for para, zh in zip(to_api, zh_list):
                used += 1
                zh = (zh or "").strip()
                last_order = max(last_order, int(para.order_index or 0))
                if not zh:
                    failed += 1
                    book_shared.mark_paragraph_translate_failed(session, para)
                    continue
                wrote = book_shared.upsert_paragraph_translation(
                    session,
                    para.edition_id,
                    para.order_index,
                    para.en_text,
                    zh,
                    source="job",
                    force=False,
                )
                if wrote:
                    crud.save_translation_cache(session, para.en_text, zh)
                    translated += 1
                    orders.append(para.order_index)
                # Existing ZH kept — still advance cursor past this paragraph.

            session.commit()
            if orders:
                book_shared.propagate_edition_to_user_docs(
                    session, eid, min(orders), max(orders)
                )

        book_shared.refresh_edition_progress(session, eid)
        session.commit()
        session.refresh(edition)

        # Durable cursor after every batch commit (edition_id + order_index).
        if on_batch:
            on_batch(edition, last_order, translated, failed)

        if edition.translate_status == "done":
            break
        if not to_api and not missing:
            break

    return translated, failed, used


def pause_stale_checkpoint() -> None:
    """Call on server boot: running jobs died with the process → mark paused for resume."""
    with Session(database.engine) as session:
        row = book_shared.get_or_create_translate_checkpoint(session)
        if row.status == "running":
            book_shared.save_translate_checkpoint(
                session,
                status="paused",
                message=row.message or "服务重启，已暂停，可继续翻译",
            )
            logger.info("book translate checkpoint paused for resume")


def get_persisted_progress() -> dict[str, Any]:
    """Merge in-memory progress with durable checkpoint for UI."""
    mem = get_backfill_progress()
    with Session(database.engine) as session:
        cp = book_shared.checkpoint_to_dict(
            book_shared.get_or_create_translate_checkpoint(session)
        )
    if mem.get("running"):
        return {**cp, **mem, "running": True, "checkpoint": cp}
    return {
        **cp,
        "running": False,
        "job_id": cp.get("job_id") or mem.get("job_id"),
        "current_book_key": cp.get("current_book_key") or mem.get("current_book_key"),
        "current_title": mem.get("current_title"),
        "books_done": cp.get("books_finished") or mem.get("books_done") or 0,
        "books_skipped": mem.get("books_skipped") or 0,
        "books_total": cp.get("books_total") or mem.get("books_total") or 0,
        "books_finished": cp.get("books_finished") or mem.get("books_finished") or 0,
        "percent": cp.get("percent") if not mem.get("running") else mem.get("percent", 0),
        "translated": cp.get("translated_paragraphs") or mem.get("translated") or 0,
        "failed": cp.get("failed_paragraphs") or mem.get("failed") or 0,
        "message": cp.get("message") or mem.get("message") or "",
        "checkpoint": cp,
        "resumable": cp.get("resumable"),
    }


async def run_backfill(
    *,
    book_key: str | None = None,
    limit: int = 200,
    batch_size: int = 20,
    max_books: int = 5,
    ensure_catalog: bool = True,
    full_run: bool = False,
    job_id: int | None = None,
) -> dict:
    """
    Async backfill:
    - optionally seed editions from curated catalog
    - walk books one-by-one (skip already done)
    - within each book, translate in batches
    - full_run=True: finish each pending book completely (manual「我的」触发)
    - else: stop when paragraph budget (limit) is exhausted
    """
    global _running
    if _running:
        return {"ok": False, "queued": False, "message": "补漏任务已在运行"}

    _running = True
    batch_size = max(1, min(int(batch_size), 50))
    max_books = max(1, min(int(max_books), 100))
    if full_run:
        # Soft safety cap per run; each book still finishes within its own budget
        limit = max(limit, 50_000)
        limit = min(limit, 200_000)
    else:
        limit = max(1, min(int(limit), 2000))

    translated = 0
    failed = 0
    books_done = 0
    books_skipped = 0
    books_touched: list[dict] = []
    remaining_budget = limit
    run_completed = False
    prefer_book_key: str | None = None
    should_chain = False
    # full_run without a single book_key: translate one book per slice.
    if full_run and not book_key:
        max_books = 1
        batch_size = min(int(batch_size or 20), 15)

    def _pct(finished: int, total: int) -> int:
        if total <= 0:
            return 100
        return max(0, min(100, int(finished / total * 100)))

    _set_progress(
        job_id=job_id,
        current_book_key=None,
        current_title=None,
        books_done=0,
        books_skipped=0,
        books_total=0,
        books_finished=0,
        percent=0,
        translated=0,
        failed=0,
        message="补漏任务启动中",
    )

    try:
        with Session(database.engine) as session:
            cp = book_shared.get_or_create_translate_checkpoint(session)
            resuming = full_run and cp.status in {"paused", "running"} and not book_key
            prefer_book_key = (cp.current_book_key if resuming else None) or None
            finished_base = int(cp.books_finished or 0) if resuming else 0
            if resuming:
                translated = int(cp.translated_paragraphs or 0)
                failed = int(cp.failed_paragraphs or 0)

            _update_job(
                session,
                job_id,
                status="running",
                progress=0,
                message="继续翻译…" if resuming else "扫描待译书籍…",
            )

            if ensure_catalog:
                if book_key:
                    book_shared.ensure_edition_from_catalog(session, book_key)
                else:
                    book_shared.ensure_catalog_editions(
                        session, limit=100 if full_run else max(max_books * 3, 20)
                    )

            editions = book_shared.list_editions_needing_work(
                session,
                book_key=book_key,
                prefer_book_key=prefer_book_key,
                limit=max(1, int(max_books)),
            )
            if book_key and not editions:
                ed = session.exec(
                    select(models.BookEdition).where(models.BookEdition.book_key == book_key)
                ).first()
                if ed and ed.translate_status == "done":
                    msg = f"{book_key} 已翻译完成，跳过"
                    book_shared.save_translate_checkpoint(
                        session,
                        status="done",
                        message=msg,
                        books_finished=1,
                        books_total=1,
                        clear_cursor=True,
                        job_id=job_id,
                    )
                    _set_progress(message=msg, books_skipped=1, percent=100, books_finished=1, books_total=1)
                    _update_job(session, job_id, status="done", progress=100, message=msg)
                    run_completed = True
                    return {
                        "ok": True,
                        "translated": 0,
                        "failed": 0,
                        "books_done": 0,
                        "books_skipped": 1,
                        "message": msg,
                        "resumed": resuming,
                    }

            pending_now = len(editions)
            if resuming and int(cp.books_total or 0) > 0:
                total_plan = max(int(cp.books_total or 0), finished_base + pending_now)
            else:
                total_plan = pending_now
                finished_base = 0

            book_shared.save_translate_checkpoint(
                session,
                status="running",
                books_total=total_plan,
                books_finished=finished_base,
                translated_paragraphs=translated,
                failed_paragraphs=failed,
                current_book_key=prefer_book_key or (editions[0].book_key if editions else None),
                current_edition_id=editions[0].id if editions else None,
                message=(
                    f"从断点继续：待译 {pending_now} 本"
                    if resuming
                    else f"发现 {pending_now} 本待译，开始逐本翻译"
                ),
                job_id=job_id,
            )

            _set_progress(
                books_total=total_plan,
                books_finished=finished_base,
                percent=_pct(finished_base, total_plan),
                translated=translated,
                failed=failed,
                message=(
                    f"从断点继续：待译 {pending_now} 本"
                    if resuming
                    else f"发现 {pending_now} 本待译，开始逐本翻译"
                ),
            )
            if not editions:
                msg = "没有需要补漏的书籍"
                book_shared.save_translate_checkpoint(
                    session,
                    status="done",
                    message=msg,
                    books_finished=total_plan or books_done,
                    clear_cursor=True,
                    job_id=job_id,
                )
                _update_job(session, job_id, status="done", progress=100, message=msg)
                _set_progress(message=msg, percent=100)
                run_completed = True
                return {
                    "ok": True,
                    "translated": 0,
                    "failed": 0,
                    "books_done": 0,
                    "books_skipped": 0,
                    "message": msg,
                    "resumed": resuming,
                }

            for idx, edition in enumerate(editions):
                if not full_run and remaining_budget <= 0:
                    break

                session.refresh(edition)
                if edition.translate_status == "done":
                    books_skipped += 1
                    finished = finished_base + books_done + books_skipped
                    books_touched.append(
                        {
                            "book_key": edition.book_key,
                            "title": edition.title,
                            "status": "skipped_done",
                        }
                    )
                    book_shared.save_translate_checkpoint(
                        session,
                        status="running",
                        books_finished=finished,
                        books_total=total_plan,
                        clear_cursor=False,
                        current_book_key=edition.book_key,
                        message=f"已跳过完成书：{edition.book_key}",
                        job_id=job_id,
                    )
                    _set_progress(
                        books_skipped=books_skipped,
                        books_finished=finished,
                        percent=_pct(finished, total_plan),
                    )
                    continue

                def _on_batch(ed, last_order, batch_translated, batch_failed, _edition=edition):
                    nonlocal translated, failed
                    # batch_translated/failed are cumulative within this book call; use deltas via outer accum later
                    book_shared.save_translate_checkpoint(
                        session,
                        status="running",
                        current_book_key=_edition.book_key,
                        current_edition_id=_edition.id,
                        current_order_index=last_order,
                        books_total=total_plan,
                        books_finished=finished_base + books_done + books_skipped,
                        translated_paragraphs=translated + batch_translated,
                        failed_paragraphs=failed + batch_failed,
                        message=(
                            f"断点：{_edition.title or _edition.book_key} "
                            f"@{last_order}（{_edition.translated_blocks}/{_edition.block_count}）"
                        ),
                        job_id=job_id,
                    )
                    _set_progress(
                        current_book_key=_edition.book_key,
                        current_title=_edition.title,
                        translated=translated + batch_translated,
                        failed=failed + batch_failed,
                        message=(
                            f"正在翻译（{idx + 1}/{len(editions)}）："
                            f"{_edition.title or _edition.book_key} "
                            f"{_edition.translated_blocks}/{_edition.block_count}"
                        ),
                    )

                _set_progress(
                    current_book_key=edition.book_key,
                    current_title=edition.title,
                    books_done=books_done,
                    books_skipped=books_skipped,
                    books_finished=finished_base + books_done + books_skipped,
                    percent=_pct(finished_base + books_done + books_skipped, total_plan),
                    message=f"正在翻译（{idx + 1}/{len(editions)}）：{edition.title or edition.book_key}",
                )
                book_shared.save_translate_checkpoint(
                    session,
                    status="running",
                    current_book_key=edition.book_key,
                    current_edition_id=edition.id,
                    books_total=total_plan,
                    books_finished=finished_base + books_done + books_skipped,
                    translated_paragraphs=translated,
                    failed_paragraphs=failed,
                    message=f"正在翻译：{edition.title or edition.book_key}",
                    job_id=job_id,
                )
                _update_job(
                    session,
                    job_id,
                    status="running",
                    progress=_pct(finished_base + books_done + books_skipped, total_plan),
                    message=f"逐本翻译中：{edition.title or edition.book_key}",
                )

                if full_run:
                    if _paragraph_count(session, edition.id) == 0:
                        filled = book_shared.ensure_edition_from_catalog(
                            session, edition.book_key
                        )
                        if filled:
                            edition = filled
                    missing_left = len(
                        book_shared.list_missing_paragraphs(
                            session, edition_id=edition.id, limit=500
                        )
                    )
                    book_budget = max(
                        int(edition.block_count or 0) - int(edition.translated_blocks or 0) + 50,
                        missing_left + 50,
                        200,
                    )
                    book_budget = min(book_budget, remaining_budget)
                else:
                    if _paragraph_count(session, edition.id) == 0:
                        filled = book_shared.ensure_edition_from_catalog(
                            session, edition.book_key
                        )
                        if filled:
                            edition = filled
                    book_budget = remaining_budget

                t, f, used = await _translate_edition_batches(
                    session,
                    edition,
                    batch_size=batch_size,
                    paragraph_budget=book_budget,
                    on_batch=_on_batch,
                )
                if full_run:
                    session.refresh(edition)
                    guard = 0
                    while edition.translate_status != "done" and guard < 200:
                        more = book_shared.list_missing_paragraphs(
                            session, edition_id=edition.id, limit=1
                        )
                        if not more:
                            book_shared.refresh_edition_progress(session, edition.id)
                            session.commit()
                            session.refresh(edition)
                            break
                        t2, f2, used2 = await _translate_edition_batches(
                            session,
                            edition,
                            batch_size=batch_size,
                            paragraph_budget=batch_size * 5,
                            on_batch=_on_batch,
                        )
                        t += t2
                        f += f2
                        used += used2
                        session.refresh(edition)
                        guard += 1

                translated += t
                failed += f
                remaining_budget = max(0, remaining_budget - used)
                session.refresh(edition)

                status = edition.translate_status
                if status == "done":
                    books_done += 1
                finished = finished_base + books_done + books_skipped
                books_touched.append(
                    {
                        "book_key": edition.book_key,
                        "title": edition.title,
                        "status": status,
                        "translated_blocks": edition.translated_blocks,
                        "block_count": edition.block_count,
                        "paragraphs_this_run": t,
                    }
                )
                book_shared.save_translate_checkpoint(
                    session,
                    status="running",
                    current_book_key=edition.book_key,
                    current_edition_id=edition.id,
                    current_order_index=int(edition.translated_blocks or 0),
                    books_total=total_plan,
                    books_finished=finished,
                    translated_paragraphs=translated,
                    failed_paragraphs=failed,
                    message=(
                        f"已完成：{edition.title or edition.book_key}"
                        if status == "done"
                        else f"暂停点：{edition.title or edition.book_key}"
                    ),
                    job_id=job_id,
                )
                _set_progress(
                    books_done=books_done,
                    books_skipped=books_skipped,
                    books_finished=finished,
                    percent=_pct(finished, total_plan),
                    translated=translated,
                    failed=failed,
                )

            msg = (
                f"本轮完成：处理 {len(books_touched)} 本，译完 {books_done} 本，"
                f"跳过 {books_skipped} 本，新译 {translated} 段，失败 {failed} 段"
            )
            still_pending = book_shared.list_editions_needing_work(session, limit=1)
            final_status = "done" if not still_pending else "paused"
            if final_status == "done":
                msg = "全部书籍翻译完成"
            else:
                msg = f"{msg}；将自动继续下一本" if full_run and not book_key else f"{msg}；未完成，可继续"
            # Keep cursor on next pending book for resume/chain.
            next_key = still_pending[0].book_key if still_pending else None
            next_eid = still_pending[0].id if still_pending else None
            book_shared.save_translate_checkpoint(
                session,
                status=final_status,
                books_finished=finished_base + books_done + books_skipped,
                books_total=total_plan,
                translated_paragraphs=translated,
                failed_paragraphs=failed,
                message=msg,
                current_book_key=next_key,
                current_edition_id=next_eid,
                clear_cursor=(final_status == "done"),
                job_id=job_id,
            )
            _update_job(session, job_id, status="done" if final_status == "done" else "paused", progress=100 if final_status == "done" else _pct(finished_base + books_done + books_skipped, total_plan), message=msg)
            _set_progress(
                current_book_key=None if final_status == "done" else next_key,
                current_title=None,
                message=msg,
                books_done=books_done,
                books_skipped=books_skipped,
                books_finished=finished_base + books_done + books_skipped,
                percent=100 if final_status == "done" else _pct(finished_base + books_done + books_skipped, total_plan),
                translated=translated,
                failed=failed,
            )
            should_chain = bool(
                full_run and not book_key and final_status == "paused" and still_pending
            )
            run_completed = True
            return {
                "ok": True,
                "translated": translated,
                "failed": failed,
                "books_done": books_done,
                "books_skipped": books_skipped,
                "books": books_touched,
                "paragraph_budget_left": remaining_budget,
                "message": msg,
                "resumed": resuming,
                "checkpoint_status": final_status,
                "will_continue": should_chain,
            }
    except Exception as e:
        logger.exception("book translate backfill failed")
        with Session(database.engine) as session:
            _update_job(session, job_id, status="failed", message=str(e))
            book_shared.save_translate_checkpoint(
                session,
                status="paused",
                translated_paragraphs=translated,
                failed_paragraphs=failed,
                books_finished=finished_base + books_done + books_skipped,
                message=f"中断已保存断点，可继续：{e}",
                job_id=job_id,
            )
        _set_progress(message=f"失败：{e}")
        return {
            "ok": False,
            "translated": translated,
            "failed": failed,
            "books_done": books_done,
            "message": str(e),
            "checkpoint_status": "paused",
        }
    finally:
        _running = False
        _set_progress(running=False)
        if not run_completed:
            with Session(database.engine) as session:
                row = book_shared.get_or_create_translate_checkpoint(session)
                if row.status == "running":
                    book_shared.save_translate_checkpoint(
                        session,
                        status="paused",
                        message=row.message or "任务已暂停，可继续翻译",
                        job_id=job_id,
                    )
        if should_chain:
            logger.info("chaining next book-translate slice (max_books=1)")
            start_backfill(
                book_key=None,
                limit=limit,
                batch_size=batch_size,
                max_books=1,
                ensure_catalog=False,
                full_run=True,
                job_id=job_id,
            )


def start_backfill(
    *,
    book_key: str | None = None,
    limit: int = 200,
    batch_size: int = 20,
    max_books: int = 5,
    ensure_catalog: bool = True,
    full_run: bool = False,
    job_id: int | None = None,
):
    from app.services.reading_processor import _schedule

    _schedule(
        run_backfill(
            book_key=book_key,
            limit=limit,
            batch_size=batch_size,
            max_books=max_books,
            ensure_catalog=ensure_catalog,
            full_run=full_run,
            job_id=job_id,
        )
    )
