from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app import crud, models, schemas, security
from app import database
from app.config import settings
from app.services import book_shared, book_translate_jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[schemas.JobRead])
def list_jobs(
    status: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    return crud.list_jobs(
        session,
        status=status,
        target_type=target_type,
        target_id=target_id,
    )


@router.post("/book-translate/backfill")
async def backfill_book_translations(
    book_key: str | None = Query(None, description="指定书 key，如 pg_11；空则全局逐本补漏"),
    limit: int = Query(200, ge=1, le=200000, description="本轮段落预算；full_run 时会自动抬高"),
    batch_size: int = Query(20, ge=1, le=50, description="每批调用翻译 API 的段落数"),
    max_books: int = Query(5, ge=1, le=100, description="本轮最多处理几本未完成的书"),
    ensure_catalog: bool = Query(True, description="是否从经典目录种子化共享书版"),
    full_run: bool = Query(False, description="true=人工触发：待译书逐本翻完"),
    sync: bool = Query(False, description="true 时同步等待本轮结果（调试用）"),
    session: Session = Depends(database.session_dependency),
):
    """人工点击触发书籍翻译补漏（异步）：逐本批量翻译并落库，已完成跳过。"""
    if book_translate_jobs.is_backfill_running():
        raise HTTPException(status_code=409, detail="补漏任务已在运行")

    user_id = security.get_current_user_id(required=False) or 1
    if full_run and not book_key:
        # Seed first so scan counts are accurate for this run.
        # One book per worker slice — long full-library runs get killed on free Render.
        if ensure_catalog:
            book_shared.ensure_catalog_editions(session, limit=100)
        max_books = 1
        batch_size = min(batch_size, 15)

    edition = None
    if book_key:
        edition = book_shared.pick_edition_needing_work(session, book_key=book_key)

    job = crud.create_job(
        session,
        "book_translate_backfill",
        target_type="book_edition",
        target_id=edition.id if edition else None,
        payload={
            "book_key": book_key,
            "limit": limit,
            "batch_size": batch_size,
            "max_books": max_books,
            "ensure_catalog": ensure_catalog,
            "full_run": full_run,
            "mode": "backfill_by_book",
        },
        user_id=user_id,
    )

    kwargs = dict(
        book_key=book_key,
        limit=limit,
        batch_size=batch_size,
        max_books=max_books,
        ensure_catalog=ensure_catalog,
        full_run=full_run,
        job_id=job.id,
    )

    if sync or not settings.inline_worker:
        result = await book_translate_jobs.run_backfill(**kwargs)
        return {"ok": True, "job_id": job.id, **result}

    book_translate_jobs.start_backfill(**kwargs)
    return {
        "ok": True,
        "queued": True,
        "job_id": job.id,
        "book_key": book_key,
        "limit": limit,
        "batch_size": batch_size,
        "max_books": max_books,
        "full_run": full_run,
        "message": "补漏任务已异步排队：将逐本批量翻译，已完成的书会跳过",
    }


@router.get("/book-translate/status")
def book_translate_status(
    book_key: str | None = Query(None),
    ensure_catalog: bool = Query(False, description="扫描前是否种子化经典目录"),
    session: Session = Depends(database.session_dependency),
):
    """扫描待译本数 + 当前补漏任务进度（供「我的」进度条轮询）。"""
    if ensure_catalog:
        book_shared.ensure_catalog_editions(session, limit=100)
    stats = book_shared.edition_translation_stats(session)
    stmt = select(models.BookEdition).order_by(models.BookEdition.updated_at.desc())
    if book_key:
        stmt = stmt.where(models.BookEdition.book_key == book_key)
    editions = session.exec(stmt.limit(50)).all()
    progress = book_translate_jobs.get_persisted_progress()
    return {
        "running": book_translate_jobs.is_backfill_running(),
        "scan": stats,
        "progress": progress,
        "checkpoint": progress.get("checkpoint"),
        "resumable": bool(progress.get("resumable")),
        "editions": [
            {
                "id": e.id,
                "book_key": e.book_key,
                "title": e.title,
                "block_count": e.block_count,
                "translated_blocks": e.translated_blocks,
                "translate_status": e.translate_status,
                "updated_at": e.updated_at,
            }
            for e in editions
        ],
    }


@router.get("/{job_id}", response_model=schemas.JobRead)
def get_job(job_id: int, session: Session = Depends(database.session_dependency)):
    job = crud.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job 不存在")
    return job
