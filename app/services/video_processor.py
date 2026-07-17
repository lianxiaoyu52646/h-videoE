"""
视频字幕加工 — 快路径：仅 CC/AI 字幕，立即可学；翻译后台异步补全。
Whisper 仅通过 process_whisper_job 手动触发。
"""
import asyncio
from threading import Lock
from typing import Callable, Optional

from sqlmodel import Session

from app import crud
from app import database
from app.models import Job, Subtitle, Video
from app.services import subtitle_fetcher, translator

_sse_publish: Optional[Callable[[int, str, dict], None]] = None
_translating: set[int] = set()
_whisper_max_seconds = 600  # 手动 Whisper 最长 10 分钟
_translation_focus: dict[int, dict] = {}
_translation_focus_lock = Lock()


def set_sse_publisher(fn: Callable[[int, str, dict], None]):
    global _sse_publish
    _sse_publish = fn


def is_translating(video_id: int) -> bool:
    return video_id in _translating


def set_translation_focus(
    video_id: int,
    *,
    anchor_id: int | None = None,
    subtitle_ids: list[int] | None = None,
) -> int:
    normalized_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in subtitle_ids or []:
        try:
            subtitle_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if subtitle_id <= 0 or subtitle_id in seen:
            continue
        seen.add(subtitle_id)
        normalized_ids.append(subtitle_id)
        if len(normalized_ids) >= 160:
            break

    with _translation_focus_lock:
        _translation_focus[video_id] = {
            "anchor_id": int(anchor_id) if anchor_id else None,
            "subtitle_ids": normalized_ids,
        }
    return len(normalized_ids)


def clear_translation_focus(video_id: int) -> None:
    with _translation_focus_lock:
        _translation_focus.pop(video_id, None)


def _translation_focus_snapshot(video_id: int) -> tuple[int | None, list[int]]:
    with _translation_focus_lock:
        payload = dict(_translation_focus.get(video_id) or {})
    anchor_id = payload.get("anchor_id")
    subtitle_ids = list(payload.get("subtitle_ids") or [])
    return anchor_id, subtitle_ids


def ensure_translation_task(video_id: int, job_id: int | None = None) -> bool:
    if video_id in _translating:
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    loop.create_task(_translate_all(video_id, job_id=job_id))
    return True


def _publish(video_id: int, event: str, data: dict):
    if _sse_publish:
        _sse_publish(video_id, event, data)


def _status_payload(status: str, message: str, progress: int, subtitle_count: int = 0) -> dict:
    return {
        "status": status,
        "message": message,
        "progress": progress,
        "phase": crud._video_learn_phase(status, subtitle_count),
    }


def _update_job(
    video_id: int,
    *,
    job_id: int | None = None,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    duration: float | None = None,
):
    with Session(database.engine) as db:
        video = db.get(Video, video_id)
        if not video:
            return
        if status is not None:
            video.subtitle_status = status
        if progress is not None:
            video.progress = max(0, min(100, progress))
        if message is not None:
            video.status_message = message
        if duration is not None:
            video.duration_seconds = duration
        target_job_id = job_id or video.active_job_id
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
        db.add(video)
        db.commit()


def _save_batch(video_id: int, batch: list[dict]) -> list:
    with Session(database.engine) as db:
        items = []
        for seg in batch:
            items.append(Subtitle(
                video_id=video_id,
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
                translation=seg.get("translation"),
            ))
        db.add_all(items)
        db.commit()
        for item in items:
            db.refresh(item)
        return items


def _no_cc_message(video: Video | None) -> str:
    title = (video.title if video else "") or ""
    if any(k in title for k in ("中字", "中文字幕", "硬字幕", "内嵌")):
        return "硬字幕视频：画面里的中字无法提取。请换有 CC/AI 字幕轨的视频，或安装 Chrome 插件在原页学习。"
    return "该视频没有 CC/AI 字幕轨道，请换一个有 CC 字幕的视频。"


def _publish_subtitles(video_id: int, saved: list):
    for sub in saved:
        _publish(video_id, "subtitle", {
            "id": sub.id, "video_id": sub.video_id,
            "start": sub.start, "end": sub.end,
            "text": sub.text, "translation": sub.translation,
        })


async def process_video_job(job_id: int | None, video_id: int, url: str, source: str):
    """快路径：只拉 CC/AI 字幕，有则立即可学，翻译异步。"""
    try:
        with Session(database.engine) as db:
            video = db.get(Video, video_id)
            user_id = video.user_id if video else None
        _update_job(video_id, job_id=job_id, status="processing", progress=10, message="正在获取字幕...")
        _publish(video_id, "status", _status_payload("processing", "正在获取字幕...", 10))

        duration = await subtitle_fetcher.fetch_video_duration(url, source, user_id=user_id)
        if duration:
            _update_job(video_id, job_id=job_id, duration=duration)

        segments = await subtitle_fetcher.fetch_subtitles(
            url,
            source,
            allow_whisper=False,
            user_id=user_id,
        )

        if not segments:
            with Session(database.engine) as db:
                video = db.get(Video, video_id)
            msg = _no_cc_message(video)
            _update_job(video_id, job_id=job_id, status="failed", progress=100, message=msg)
            _publish(video_id, "status", _status_payload("failed", msg, 100))
            _publish(video_id, "error", {"message": msg})
            _publish(video_id, "done", {"message": msg, "total": 0})
            return

        _update_job(video_id, job_id=job_id, progress=70, message=f"已获取 {len(segments)} 条字幕，保存中...")
        saved = _save_batch(video_id, segments)
        _publish_subtitles(video_id, saved)

        _update_job(
            video_id, job_id=job_id, status="ready", progress=80,
            message="字幕已就绪，可以开始学习（中文翻译后台进行中）",
        )
        _publish(video_id, "status", _status_payload("ready", "可以开始学习", 80, len(saved)))
        _publish(video_id, "ready", {"message": "可以开始学习", "total": len(saved), "phase": "subtitleReady"})

        ensure_translation_task(video_id, job_id=job_id)

    except Exception as e:
        print(f"[processor] job failed video {video_id}: {e}")
        _update_job(video_id, job_id=job_id, status="failed", message=str(e))
        _publish(video_id, "error", {"message": str(e)})


async def process_whisper_job(job_id: int | None, video_id: int, url: str, source: str):
    """手动 Whisper：仅短视频，耗时长。"""
    try:
        with Session(database.engine) as db:
            video = db.get(Video, video_id)
        user_id = video.user_id if video else None
        duration = (video.duration_seconds if video else 0) or await subtitle_fetcher.fetch_video_duration(
            url,
            source,
            user_id=user_id,
        )
        if duration and duration > _whisper_max_seconds:
            msg = f"视频过长（{int(duration // 60)} 分钟），语音识别仅支持 10 分钟以内。"
            _update_job(video_id, job_id=job_id, status="failed", message=msg)
            _publish(video_id, "error", {"message": msg})
            return

        if duration:
            _update_job(video_id, job_id=job_id, duration=duration)

        _update_job(video_id, job_id=job_id, status="processing", progress=5, message="语音识别中（较慢）...")
        _publish(video_id, "status", _status_payload("processing", "语音识别中...", 5))

        total_est = duration or 600
        whisper_count = 0

        def on_whisper_batch(batch: list[dict]):
            nonlocal whisper_count
            saved = _save_batch(video_id, batch)
            whisper_count += len(saved)
            _publish_subtitles(video_id, saved)
            last_end = batch[-1]["end"] if batch else 0
            pct = min(75, int(10 + (last_end / total_est) * 65))
            msg = f"语音识别中... {whisper_count} 条"
            _update_job(video_id, job_id=job_id, progress=pct, message=msg, status="processing")
            _publish(video_id, "status", _status_payload("processing", msg, pct))

        segments = await subtitle_fetcher.fetch_subtitles_whisper(
            url,
            source,
            on_batch=on_whisper_batch,
            user_id=user_id,
        )

        with Session(database.engine) as db:
            saved = crud.get_subtitles(db, video_id)
        if not saved and segments:
            saved = _save_batch(video_id, segments)
            _publish_subtitles(video_id, saved)

        if not saved:
            msg = "语音识别失败，请检查链接或 B 站登录状态。"
            _update_job(video_id, job_id=job_id, status="failed", progress=100, message=msg)
            _publish(video_id, "error", {"message": msg})
            _publish(video_id, "done", {"message": msg, "total": 0})
            return

        _update_job(video_id, job_id=job_id, status="ready", progress=80, message="识别完成，可以开始学习")
        _publish(video_id, "status", _status_payload("ready", "可以开始学习", 80, len(saved)))
        _publish(video_id, "ready", {"message": "可以开始学习", "total": len(saved), "phase": "subtitleReady"})
        ensure_translation_task(video_id, job_id=job_id)

    except Exception as e:
        print(f"[processor] whisper failed video {video_id}: {e}")
        _update_job(video_id, job_id=job_id, status="failed", message=str(e))
        _publish(video_id, "error", {"message": str(e)})


async def _translate_all(video_id: int, job_id: int | None = None):
    if video_id in _translating:
        return
    _translating.add(video_id)
    try:
        with Session(database.engine) as db:
            saved = crud.get_subtitles(db, video_id)
        if not saved:
            return
        if all(getattr(s, "translation", None) for s in saved):
            _update_job(video_id, job_id=job_id, status="done", progress=100, message="完成，可以开始学习")
            _publish(video_id, "status", _status_payload("done", "字幕已就绪", 100, len(saved)))
            _publish(video_id, "done", {"message": "完成", "total": len(saved), "phase": "reviewReady"})
            return

        _update_job(video_id, job_id=job_id, status="translating", progress=90, message="正在翻译字幕...")
        _publish(video_id, "status", _status_payload("translating", "正在翻译字幕...", 90, len(saved)))

        BATCH = 24
        total = len(saved)
        index_by_id = {sub.id: idx for idx, sub in enumerate(saved) if sub.id is not None}
        pending_by_id = {
            sub.id: sub
            for sub in saved
            if sub.id is not None and not getattr(sub, "translation", None)
        }

        while pending_by_id:
            batch = _pick_translation_batch(
                video_id,
                list(pending_by_id.values()),
                index_by_id,
                batch_size=BATCH,
            )
            if not batch:
                break
            segments = [{"start": s.start, "end": s.end, "text": s.text} for s in batch]
            translated = await translator.translate_subtitles(segments)
            with Session(database.engine) as db:
                for i, sub in enumerate(batch):
                    if i < len(translated) and translated[i].get("translation"):
                        db_sub = db.get(Subtitle, sub.id)
                        if db_sub:
                            db_sub.translation = translated[i]["translation"]
                            db.add(db_sub)
                            _publish(video_id, "translated", {
                                "id": sub.id, "translation": translated[i]["translation"],
                            })
                    pending_by_id.pop(sub.id, None)
                db.commit()

            translated_count = total - len(pending_by_id)
            progress = min(99, 90 + int((translated_count / max(total, 1)) * 9))
            _update_job(
                video_id,
                job_id=job_id,
                status="translating",
                progress=progress,
                message=f"正在翻译字幕... {translated_count}/{total}",
            )
            _publish(
                video_id,
                "status",
                _status_payload("translating", f"正在翻译字幕... {translated_count}/{total}", progress, total),
            )

        _update_job(video_id, job_id=job_id, status="done", progress=100, message="完成，可以开始学习")
        _publish(video_id, "status", _status_payload("done", "字幕已就绪", 100, total))
        _publish(video_id, "done", {"message": "完成", "total": total, "phase": "reviewReady"})
    finally:
        _translating.discard(video_id)
        clear_translation_focus(video_id)


def _pick_translation_batch(
    video_id: int,
    pending: list[Subtitle],
    index_by_id: dict[int, int],
    *,
    batch_size: int,
) -> list[Subtitle]:
    if not pending:
        return []

    anchor_id, focus_ids = _translation_focus_snapshot(video_id)
    if not focus_ids:
        return sorted(pending, key=lambda sub: index_by_id.get(sub.id or 0, 10**9))[:batch_size]

    focus_order = {subtitle_id: pos for pos, subtitle_id in enumerate(focus_ids)}
    focus_set = set(focus_order)
    anchor_index = index_by_id.get(anchor_id) if anchor_id is not None else None

    def sort_key(sub: Subtitle) -> tuple[int, int, int]:
        sub_id = sub.id or 0
        base_index = index_by_id.get(sub_id, 10**9)
        if sub_id in focus_set:
            if anchor_index is not None:
                return (0, abs(base_index - anchor_index), base_index)
            return (0, focus_order.get(sub_id, base_index), base_index)
        return (1, base_index, base_index)

    return sorted(pending, key=sort_key)[:batch_size]
