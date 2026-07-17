from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session, select

from app import crud, database, models, security
from app.config import settings
from app.services import reading_processor, video_processor

logger = logging.getLogger("videoenglish.worker")


def _job_priority(kind: str) -> tuple[int, int]:
    """桌面单用户模式下，优先尽快启动视频任务，避免长篇阅读翻译把视频卡在排队中。"""
    if kind.startswith("video_"):
        return (0, 0)
    if kind.startswith("reading_"):
        return (1, 0)
    return (2, 0)


async def _run_job(job_id: int) -> None:
    with Session(database.engine) as session:
        job = session.get(models.Job, job_id)
        if not job or job.status != "pending":
            return
        job.status = "running"
        job.started_at = crud._utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)

        kind = job.kind
        payload = job.payload_json or {}
        target_id = job.target_id

    try:
        if kind == "video_subtitles":
            with Session(database.engine) as session:
                video = session.get(models.Video, target_id)
            if not video:
                raise RuntimeError("视频不存在")
            await video_processor.process_video_job(job_id, video.id, video.url, video.source)
            return

        if kind == "video_whisper":
            with Session(database.engine) as session:
                video = session.get(models.Video, target_id)
            if not video:
                raise RuntimeError("视频不存在")
            await video_processor.process_whisper_job(job_id, video.id, video.url, video.source)
            return

        if kind == "reading_translate":
            with Session(database.engine) as session:
                doc = session.get(models.ReadingDocument, target_id)
            if not doc:
                raise RuntimeError("文档不存在")
            if payload.get("mode") == "chapter":
                await reading_processor.run_chapter_job(
                    doc.id,
                    int(payload.get("chapter_index", 0)),
                    prefetch_next=bool(payload.get("prefetch_next")),
                    job_id=job_id,
                )
            elif payload.get("mode") == "fill_missing":
                await reading_processor.translate_document(
                    doc.id,
                    force=False,
                    job_id=job_id,
                    replace=True,
                )
            else:
                await reading_processor.translate_document(
                    doc.id,
                    force=bool(payload.get("force")),
                    job_id=job_id,
                )
            return

        raise RuntimeError(f"未知 Job 类型: {kind}")
    except Exception as exc:
        logger.exception("job %s failed", job_id)
        with Session(database.engine) as session:
            crud.update_job_progress(
                session,
                job_id,
                status="failed",
                progress=100,
                message=str(exc),
            )


async def run_forever(poll_seconds: float = 2.0, max_concurrent: int = 3) -> None:
    database.init_db()
    if settings.local_auto_user:
        security.ensure_default_user_exists()
    running: dict[int, asyncio.Task] = {}
    while True:
        finished = [job_id for job_id, task in running.items() if task.done()]
        for job_id in finished:
            task = running.pop(job_id)
            try:
                await task
            except Exception:
                logger.exception("background job task %s failed", job_id)

        slots = max_concurrent - len(running)
        if slots > 0:
            with Session(database.engine) as session:
                pending_jobs = session.exec(
                    select(models.Job)
                    .where(models.Job.status == "pending")
                    .order_by(models.Job.created_at.asc())
                ).all()
            pending_jobs.sort(key=lambda job: (_job_priority(job.kind), job.created_at))
            for job in pending_jobs:
                if slots <= 0:
                    break
                if job.id in running:
                    continue
                running[job.id] = asyncio.create_task(_run_job(job.id))
                slots -= 1

        await asyncio.sleep(poll_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
