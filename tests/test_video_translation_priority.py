from sqlmodel import Session

from app import models
from app.services import video_processor


def _make_subtitle(idx: int) -> models.Subtitle:
    return models.Subtitle(
        id=idx,
        video_id=1,
        start=float(idx),
        end=float(idx) + 1,
        text=f"subtitle {idx}",
    )


def test_pick_translation_batch_prefers_focus_window():
    video_id = 99
    pending = [_make_subtitle(idx) for idx in range(1, 9)]
    index_by_id = {sub.id: pos for pos, sub in enumerate(pending)}

    try:
        video_processor.set_translation_focus(
            video_id,
            anchor_id=6,
            subtitle_ids=[4, 5, 6, 7],
        )
        batch = video_processor._pick_translation_batch(
            video_id,
            pending,
            index_by_id,
            batch_size=4,
        )
        assert [sub.id for sub in batch] == [6, 5, 7, 4]
    finally:
        video_processor.clear_translation_focus(video_id)


def test_pick_translation_batch_without_focus_keeps_original_order():
    video_id = 100
    pending = [_make_subtitle(idx) for idx in range(1, 6)]
    index_by_id = {sub.id: pos for pos, sub in enumerate(pending)}

    batch = video_processor._pick_translation_batch(
        video_id,
        pending,
        index_by_id,
        batch_size=3,
    )
    assert [sub.id for sub in batch] == [1, 2, 3]


def test_translation_focus_endpoint_records_ids(client, test_engine, monkeypatch):
    captured = {}

    def _fake_ensure(video_id: int, job_id: int | None = None) -> bool:
        captured["video_id"] = video_id
        captured["job_id"] = job_id
        return True

    monkeypatch.setattr(video_processor, "ensure_translation_task", _fake_ensure)

    with Session(test_engine) as session:
        video = models.Video(
            url="https://www.bilibili.com/video/BV1test?p=3",
            source="bilibili",
            video_id="BV1test",
            subtitle_status="ready",
            active_job_id=321,
        )
        session.add(video)
        session.commit()
        session.refresh(video)

    resp = client.post(
        f"/api/videos/{video.id}/translation-focus",
        json={"anchor_id": 11, "subtitle_ids": [11, 12, 13]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["accepted"] == 3
    assert captured == {"video_id": video.id, "job_id": 321}

    video_processor.clear_translation_focus(video.id)
