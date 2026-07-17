"""reading_processor 并发与完成率测试"""
import asyncio

import pytest
from sqlmodel import Session, select

from app.models import ReadingBlock, ReadingDocument


@pytest.fixture(autouse=True)
def _no_bg(monkeypatch):
    monkeypatch.setattr("app.routers.readings._start_translate", lambda doc_id, force=False: None)


def _create_doc(client, text="Hello world.\n\nSecond paragraph."):
    r = client.post("/api/readings", json={
        "title": "Processor test",
        "content": text,
        "source_type": "paste",
    })
    assert r.status_code == 200
    return r.json()["id"]


def test_translate_marks_failed_when_mostly_empty(client, test_engine, monkeypatch):
    async def _empty(texts):
        return [""] * len(texts)

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _empty,
    )
    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_text",
        lambda text, source="en", target="zh-CN": "",
    )
    doc_id = _create_doc(client, "One.\n\nTwo.\n\nThree.")

    from app.services.reading_processor import translate_document
    asyncio.run(translate_document(doc_id))

    doc = client.get(f"/api/readings/{doc_id}").json()
    assert doc["translate_status"] == "failed"
    assert "0/3" in doc.get("status_message", "") or "失败" in doc.get("status_message", "")


def test_force_retranslate_cancels_stale_run(client, test_engine, monkeypatch):
    gate = asyncio.Event()
    calls = {"n": 0}

    async def _slow(texts):
        calls["n"] += 1
        n = calls["n"]
        if n == 1:
            await gate.wait()
        return [f"【译】{t}" for t in texts]

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _slow,
    )
    doc_id = _create_doc(client, "Alpha.\n\nBeta.")

    from app.services.reading_processor import translate_document

    async def _run_concurrent():
        t1 = asyncio.create_task(translate_document(doc_id))
        await asyncio.sleep(0.05)
        t2 = asyncio.create_task(translate_document(doc_id, force=True))
        gate.set()
        await asyncio.gather(t1, t2)

    asyncio.run(_run_concurrent())

    with Session(test_engine) as db:
        blocks = list(db.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all())
        doc = db.get(ReadingDocument, doc_id)
    assert doc.translate_status == "done"
    assert all((b.translation or "").startswith("【译】") for b in blocks if b.text.strip())


def test_retry_untranslated_blocks_can_recover_document(client, test_engine, monkeypatch):
    async def _first_pass_empty(texts):
        return [""] * len(texts)

    def _retry_single(text, source="en", target="zh-CN"):
        return f"【补译】{text}"

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _first_pass_empty,
    )
    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_text",
        _retry_single,
    )
    doc_id = _create_doc(client, "Alpha paragraph.\n\nBeta paragraph.")

    from app.services.reading_processor import translate_document
    asyncio.run(translate_document(doc_id))

    with Session(test_engine) as db:
        blocks = list(db.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all())
        doc = db.get(ReadingDocument, doc_id)
    assert doc.translate_status == "done"
    assert all((b.translation or "").startswith("【补译】") for b in blocks if b.text.strip())


def test_retranslate_keeps_existing_translations(client, test_engine, monkeypatch):
    from app import models
    from app.routers.readings import _create_translate_job

    monkeypatch.setattr(
        "app.routers.readings._start_translate",
        lambda doc_id, force=False: _create_translate_job(doc_id, force=force),
    )
    monkeypatch.setattr(
        "app.routers.readings.reading_processor.start_untranslated_translation",
        lambda doc_id, job_id=None: _create_translate_job(doc_id, force=False),
    )

    doc_id = _create_doc(client, "Line one.\n\nLine two.")

    with Session(test_engine) as session:
        blocks = session.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all()
        for block in blocks:
            block.translation = f"旧译文-{block.order_index}"
            session.add(block)
        doc = session.get(ReadingDocument, doc_id)
        doc.translate_status = "done"
        doc.translate_progress = 100
        doc.translated_blocks = len(blocks)
        doc.status_message = "翻译完成（1 段未译出，可重试）"
        session.add(doc)
        session.commit()

    retranslate_resp = client.post(f"/api/readings/{doc_id}/translate")
    assert retranslate_resp.status_code == 200, retranslate_resp.text
    body = retranslate_resp.json()
    assert body.get("queued") is False

    with Session(test_engine) as session:
        blocks = session.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all()
        assert all((block.translation or "").startswith("旧译文-") for block in blocks)
        jobs = session.exec(
            select(models.Job).where(
                models.Job.kind == "reading_translate",
                models.Job.target_id == doc_id,
            )
        ).all()
        assert not jobs or jobs[-1].status != "pending"


def test_retranslate_queues_missing_only(client, test_engine, monkeypatch):
    from app import models

    created_jobs: list[int] = []

    def _fake_start(doc_id, job_id=None):
        created_jobs.append(job_id)

    monkeypatch.setattr(
        "app.routers.readings.reading_processor.start_untranslated_translation",
        _fake_start,
    )

    doc_id = _create_doc(client, "Line one.\n\nLine two.")

    with Session(test_engine) as session:
        blocks = session.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all()
        blocks[0].translation = "已有译文"
        session.add(blocks[0])
        doc = session.get(ReadingDocument, doc_id)
        doc.translate_status = "ready"
        doc.translated_blocks = 1
        doc.translate_progress = 50
        session.add(doc)
        session.commit()

    resp = client.post(f"/api/readings/{doc_id}/translate")
    assert resp.status_code == 200, resp.text
    assert resp.json().get("queued") is True

    doc = client.get(f"/api/readings/{doc_id}").json()
    assert doc["translate_status"] == "pending"
    assert doc["translated_blocks"] == 1
    assert doc["active_job_id"]
    assert created_jobs

    with Session(test_engine) as session:
        blocks = session.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all()
        assert (blocks[0].translation or "") == "已有译文"
        assert not (blocks[1].translation or "").strip()


def test_lazy_chapter_translate_only_current_chapter(client, test_engine, monkeypatch):
    async def _fake(texts):
        return [f"【译】{t}" for t in texts]

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _fake,
    )
    doc_id = _create_doc(client, "Alpha one.\n\nAlpha two.\n\n<<<SECTION:Beta>>>\n\nBeta one.\n\nBeta two.")

    from tests.conftest import run_chapter_translate_sync

    run_chapter_translate_sync(doc_id, 0)

    toc = client.get(f"/api/readings/{doc_id}/toc").json()
    ch0 = toc["chapters"][0]

    with Session(test_engine) as db:
        blocks = list(db.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all())
        doc = db.get(ReadingDocument, doc_id)

    chapter0 = [b for b in blocks if ch0["start_block"] <= b.order_index <= ch0["end_block"]]
    chapter1 = [b for b in blocks if b.order_index > ch0["end_block"]]
    assert all((b.translation or "").startswith("【译】") for b in chapter0 if b.text.strip())
    assert all(not (b.translation or "").strip() for b in chapter1 if b.text.strip())
    assert doc.translate_status in ("ready", "done")
    assert doc.translate_progress < 100 or doc.block_count <= 2


def test_import_does_not_auto_translate(client, test_engine):
    doc_id = _create_doc(client, "Hello chapter.\n\nSecond line.")
    doc = client.get(f"/api/readings/{doc_id}").json()
    assert doc["translate_status"] == "ready"
    assert doc["translate_progress"] == 0

    with Session(test_engine) as db:
        blocks = list(db.exec(
            select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
        ).all())
    assert all(not (b.translation or "").strip() for b in blocks)


def test_translate_chapter_api(client, test_engine, monkeypatch):
    doc_id = _create_doc(client, "One.\n\nTwo.\n\nThree.")

    resp = client.post(f"/api/readings/{doc_id}/translate/chapter/0?prefetch_next=false")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("chapter_index") == 0
