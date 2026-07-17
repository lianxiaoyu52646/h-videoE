"""
视频 API — 视频库 + 快路径字幕 + 学习页
"""
import asyncio
import json
import re
from collections import defaultdict
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app import crud, database, schemas
from app.config import settings
from app.models import Video
from app.services import subtitle_fetcher, video_processor

router = APIRouter(prefix="/api/videos", tags=["videos"])

_sse_subscribers: Dict[int, Set[asyncio.Queue]] = defaultdict(set)
_processing: Set[int] = set()
_whisper_processing: Set[int] = set()

video_processor.set_sse_publisher(
    lambda vid, ev, data: _sse_publish(vid, ev, data)
)


def _normalize_url(url: str) -> str:
    if "bilibili.com" in url:
        m = re.search(r"/video/(BV[\w]+)", url, re.I)
        if m:
            bvid = m.group(1)
            p_match = re.search(r"[?&]p=(\d+)", url)
            p = p_match.group(1) if p_match else "1"
            return f"https://www.bilibili.com/video/{bvid}?p={p}"
    return url


def _sse_publish(video_id: int, event: str, data: dict):
    for queue in _sse_subscribers.get(video_id, []):
        try:
            queue.put_nowait((event, data))
        except asyncio.QueueFull:
            pass


def _no_subtitle_message(video: Video) -> str:
    title = video.title or video.url or ""
    if any(k in title for k in ("中字", "中文字幕", "硬字幕", "内嵌")):
        return "硬字幕视频：画面里的中字无法提取，请换有 CC/AI 字幕轨的视频。"
    return "该视频没有 CC/AI 字幕轨道，请换一个有 CC 字幕的视频。"


def _create_job(video_id: int, url: str, source: str, kind: str):
    with Session(database.engine) as session:
        video = session.get(Video, video_id)
        if not video:
            return None
        job = crud.create_job(
            session,
            kind,
            target_type="video",
            target_id=video_id,
            payload={"url": url, "source": source},
            user_id=video.user_id,
        )
        video.active_job_id = job.id
        session.add(video)
        session.commit()
        return job.id


def _start_job(video_id: int, url: str, source: str):
    if video_id in _processing:
        return
    job_id = _create_job(video_id, url, source, "video_subtitles")
    if not job_id:
        return
    if not settings.inline_worker:
        return
    _processing.add(video_id)
    task = asyncio.create_task(_run_job(job_id, video_id, url, source))
    task.add_done_callback(lambda _: _processing.discard(video_id))


async def _run_job(job_id: int, video_id: int, url: str, source: str):
    try:
        await video_processor.process_video_job(job_id, video_id, url, source)
    finally:
        _processing.discard(video_id)


def _start_whisper_job(video_id: int, url: str, source: str):
    if video_id in _whisper_processing or video_id in _processing:
        return
    job_id = _create_job(video_id, url, source, "video_whisper")
    if not job_id:
        return
    if not settings.inline_worker:
        return
    _whisper_processing.add(video_id)
    task = asyncio.create_task(_run_whisper_job(job_id, video_id, url, source))
    task.add_done_callback(lambda _: _whisper_processing.discard(video_id))


async def _run_whisper_job(job_id: int, video_id: int, url: str, source: str):
    try:
        await video_processor.process_whisper_job(job_id, video_id, url, source)
    finally:
        _whisper_processing.discard(video_id)


def _to_read(session: Session, video: Video) -> schemas.VideoRead:
    return schemas.VideoRead(**crud.video_to_read(session, video))


@router.get("", response_model=list[schemas.VideoRead])
def list_videos(session: Session = Depends(database.session_dependency)):
    videos = crud.list_videos(session)
    return [_to_read(session, v) for v in videos]


@router.post("", response_model=schemas.VideoRead)
async def add_video(request: schemas.VideoCreate, session: Session = Depends(database.session_dependency)):
    normalized = _normalize_url(request.url)
    existing = crud.get_video_by_url(session, normalized)

    if existing:
        if existing.subtitle_status in ("failed", "done", "ready") and crud.count_subtitles(session, existing.id) == 0:
            existing.subtitle_status = "pending"
            existing.progress = 0
            existing.status_message = "排队中..."
            session.add(existing)
            session.commit()
            _start_job(existing.id, existing.url, existing.source)
        elif existing.subtitle_status == "pending":
            _start_job(existing.id, existing.url, existing.source)
        return _to_read(session, existing)

    source_info = subtitle_fetcher.parse_video_url(normalized)
    video = crud.create_video(session, normalized, source_info)
    video.status_message = "排队中..."
    session.add(video)
    session.commit()
    session.refresh(video)

    if video.source == "bilibili" and video.video_id:
        try:
            title = await subtitle_fetcher.fetch_bilibili_title(video.video_id, user_id=video.user_id)
            if title:
                video.title = title
                session.add(video)
                session.commit()
                session.refresh(video)
        except Exception:
            pass

    if video.source in ("bilibili", "youtube"):
        _start_job(video.id, video.url, video.source)

    return _to_read(session, video)


@router.post("/{video_id}/refetch")
async def refetch_subtitles(video_id: int, session: Session = Depends(database.session_dependency)):
    video = crud.get_video(session, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    for s in crud.get_subtitles(session, video_id):
        session.delete(s)
    video.subtitle_status = "pending"
    video.progress = 0
    video.status_message = "重新获取字幕..."
    session.add(video)
    session.commit()
    _start_job(video.id, video.url, video.source)
    return {"ok": True}


@router.post("/{video_id}/whisper")
async def whisper_subtitles(video_id: int, session: Session = Depends(database.session_dependency)):
    """手动语音识别（慢，仅建议 10 分钟以内短视频）"""
    video = crud.get_video(session, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.source not in ("bilibili", "youtube"):
        raise HTTPException(status_code=400, detail="Unsupported source")
    for s in crud.get_subtitles(session, video_id):
        session.delete(s)
    video.subtitle_status = "pending"
    video.progress = 0
    video.status_message = "语音识别排队中..."
    session.add(video)
    session.commit()
    _start_whisper_job(video.id, video.url, video.source)
    return {"ok": True, "message": "已开始语音识别，耗时较长，请耐心等待"}


@router.get("/{video_id}", response_model=schemas.VideoRead)
def get_video(video_id: int, session: Session = Depends(database.session_dependency)):
    video = crud.get_video(session, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _to_read(session, video)


@router.get("/{video_id}/subtitles", response_model=list[schemas.SubtitleRead])
def get_subtitles(video_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_video(session, video_id):
        raise HTTPException(status_code=404, detail="Video not found")
    return crud.get_subtitles(session, video_id)


@router.post("/{video_id}/translation-focus")
async def translation_focus(
    video_id: int,
    body: schemas.SubtitleFocusRequest,
    session: Session = Depends(database.session_dependency),
):
    video = crud.get_video(session, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    accepted = video_processor.set_translation_focus(
        video_id,
        anchor_id=body.anchor_id,
        subtitle_ids=body.subtitle_ids,
    )
    if accepted and video.subtitle_status in ("ready", "translating"):
        video_processor.ensure_translation_task(video_id, job_id=video.active_job_id)
    return {"ok": True, "accepted": accepted}


@router.get("/{video_id}/subtitles/stream")
async def subtitles_stream(video_id: int, request: Request):
    with Session(database.engine) as session:
        video = crud.get_video(session, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        video_data = crud.video_to_read(session, video)
        scoped_user_id = video.user_id
        subs = crud.get_subtitles(session, video_id)
        subtitle_status = video_data["subtitle_status"]
        status_message = video_data["status_message"]
        progress = video_data["progress"]
        learn_phase = video_data["learn_phase"]
        has_cached = subtitle_status in ("done", "failed") or (
            subtitle_status in ("ready", "translating") and subs
        )
        cached_subs = [
            {
                "id": s.id, "video_id": s.video_id,
                "start": s.start, "end": s.end,
                "text": s.text, "translation": s.translation,
            }
            for s in subs
        ]
        needs_translation_resume = (
            subtitle_status in ("ready", "translating")
            and any(not (s.translation or "").strip() for s in subs)
        )
        no_sub_fallback = _no_subtitle_message(video)

    if needs_translation_resume:
        video_processor.ensure_translation_task(video_id, job_id=video.active_job_id)

    if has_cached:
        async def cached_stream():
            if cached_subs:
                st = subtitle_status
                msg = status_message or ("可以开始学习" if st in ("ready", "translating", "done") else "")
                yield f"event: status\ndata: {json.dumps({'status': st, 'message': msg, 'progress': progress or 80, 'phase': learn_phase}, ensure_ascii=False)}\n\n"
                for sub in cached_subs:
                    yield f"event: subtitle\ndata: {json.dumps(sub, ensure_ascii=False)}\n\n"
                if subtitle_status == "done":
                    yield f"event: done\ndata: {json.dumps({'message': '完成', 'total': len(cached_subs), 'phase': 'reviewReady'}, ensure_ascii=False)}\n\n"
                elif subtitle_status in ("ready", "translating") or video_processor.is_translating(video_id):
                    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
                    _sse_subscribers[video_id].add(queue)
                    try:
                        while True:
                            if await request.is_disconnected():
                                break
                            try:
                                event, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                                if event == "done":
                                    break
                            except asyncio.TimeoutError:
                                yield ": heartbeat\n\n"
                                with Session(database.engine) as session:
                                    cur = crud.get_video(session, video_id, user_id=scoped_user_id)
                                    if cur and cur.subtitle_status == "done":
                                        yield f"event: done\ndata: {json.dumps({'message': '完成', 'total': len(cached_subs), 'phase': 'reviewReady'}, ensure_ascii=False)}\n\n"
                                        break
                    finally:
                        _sse_subscribers[video_id].discard(queue)
                else:
                    yield f"event: ready\ndata: {json.dumps({'message': '可以开始学习', 'total': len(cached_subs), 'phase': 'subtitleReady'}, ensure_ascii=False)}\n\n"
            else:
                msg = status_message or no_sub_fallback
                yield f"event: status\ndata: {json.dumps({'status': subtitle_status, 'message': msg, 'progress': progress, 'phase': learn_phase}, ensure_ascii=False)}\n\n"
                yield f"event: done\ndata: {json.dumps({'message': msg, 'total': 0, 'phase': learn_phase}, ensure_ascii=False)}\n\n"

        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    if video_id not in _processing and subtitle_status == "pending":
        with Session(database.engine) as session:
            v = crud.get_video(session, video_id, user_id=scoped_user_id)
            if v:
                _start_job(v.id, v.url, v.source)

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _sse_subscribers[video_id].add(queue)

    for sub in cached_subs:
        _sse_publish(video_id, "subtitle", sub)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    if event in ("done", "error", "ready"):
                        if event == "ready":
                            continue
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            _sse_subscribers[video_id].discard(queue)
            if not _sse_subscribers[video_id]:
                del _sse_subscribers[video_id]

    return StreamingResponse(event_stream(), media_type="text/event-stream")
