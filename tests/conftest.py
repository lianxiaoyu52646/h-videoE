"""测试 fixtures — 隔离 SQLite 数据库 + FastAPI TestClient"""
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_reading_cache():
    from app.services import reading_cache
    reading_cache.clear_all()
    yield
    reading_cache.clear_all()


@pytest.fixture(autouse=True)
def _reset_translating():
    import app.services.reading_processor as rp
    rp._running_tasks.clear()
    rp._generations.clear()
    rp._chapter_queues.clear()
    rp._queue_workers.clear()
    rp._queued_chapters.clear()
    yield
    rp._running_tasks.clear()
    rp._generations.clear()
    rp._chapter_queues.clear()
    rp._queue_workers.clear()
    rp._queued_chapters.clear()


@pytest.fixture()
def test_engine(tmp_path, monkeypatch):
    db_file = tmp_path / "test.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr("app.database.engine", engine)
    import app.models  # noqa: F401 — 注册全部表
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def client(test_engine, monkeypatch):
    monkeypatch.setattr("app.services.reading_processor.engine", test_engine)
    monkeypatch.setattr("app.services.reading_processor.resume_pending_translations", lambda: None)

    def _get_session():
        with Session(test_engine) as session:
            yield session

    monkeypatch.setattr("app.database.get_session", _get_session)

    from app.database import get_session
    from app.main import app

    app.dependency_overrides[get_session] = _get_session
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture()
def mock_translate(monkeypatch):
    """Mock 段落翻译，避免 E2E 依赖外网"""

    async def _fake_paragraphs(texts):
        return [f"【译】{t[:48]}" if t else "" for t in texts]

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _fake_paragraphs,
    )


@pytest.fixture(autouse=True)
def _maybe_mock_dictionary(request, monkeypatch):
    """非 network 测试统一 mock 查词，避免 SSL/外网干扰"""
    if request.node.get_closest_marker("network"):
        return

    def _fake(word: str) -> dict:
        w = (word or "").lower()
        return {
            "word": w,
            "definition": f"Definition of {w}",
            "pronunciation": "/test/",
            "part_of_speech": "noun",
            "example": None,
            "translation": "测试词",
            "youdao_translation": "测试词",
        }

    monkeypatch.setattr("app.services.dictionary.lookup_word", _fake)
    monkeypatch.setattr("app.routers.vocabulary.dictionary.lookup_word", _fake)


@pytest.fixture()
def mock_dictionary(monkeypatch):
    def _fake(word: str) -> dict:
        w = (word or "").lower()
        return {
            "word": w,
            "definition": f"Definition of {w}",
            "pronunciation": "/test/",
            "part_of_speech": "noun",
            "example": None,
            "translation": "测试词",
            "youdao_translation": "测试词",
        }

    monkeypatch.setattr("app.services.dictionary.lookup_word", _fake)
    monkeypatch.setattr("app.routers.vocabulary.dictionary.lookup_word", _fake)


@pytest.fixture()
def wizard_story_text():
    return (FIXTURES / "wizard_story.txt").read_text(encoding="utf-8")


def wait_until_translate_done(client, doc_id: int, timeout: float = 30.0) -> dict:
    """轮询直到翻译完成或失败"""
    import time

    deadline = time.time() + timeout
    doc = None
    while time.time() < deadline:
        doc = client.get(f"/api/readings/{doc_id}").json()
        if doc.get("translate_status") in ("done", "failed"):
            return doc
        time.sleep(0.15)
    return doc or {}


def run_translate_sync(doc_id: int, force: bool = False, timeout: float = 900):
    """在测试中同步跑完全书翻译（独立线程，避免与 TestClient 事件循环死锁）"""
    import concurrent.futures

    from app.services.reading_processor import translate_document

    def _run():
        asyncio.run(translate_document(doc_id, force=force))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_run)
        fut.result(timeout=timeout)


def run_chapter_translate_sync(
    doc_id: int,
    chapter_index: int = 0,
    *,
    timeout: float = 900,
):
    """同步跑完指定章节翻译"""
    import concurrent.futures

    from app.services.reading_processor import _translate_chapter_impl

    def _thread():
        asyncio.run(_translate_chapter_impl(doc_id, chapter_index))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_thread)
        fut.result(timeout=timeout)
