"""
阅读模块 E2E 测试 — 以魔法题材样章（哈利波特风格词汇）验证全流程。

真实《哈利波特》EPUB：设置环境变量 TEST_HP_EPUB=/path/to/book.epub 后运行 test_harry_potter_epub_upload。
"""
import asyncio
import os
import time
from pathlib import Path

import pytest

from tests.conftest import FIXTURES, wait_until_translate_done


@pytest.fixture(autouse=True)
def _no_background_translate(monkeypatch):
    """测试里手动触发翻译，避免后台任务不可控"""
    monkeypatch.setattr("app.routers.readings._start_translate", lambda doc_id, force=False: None)


def _create_wizard_book(client, wizard_story_text, title="Wizard Story (HP-style E2E)"):
    r = client.post("/api/readings", json={
        "title": title,
        "content": wizard_story_text,
        "source_type": "paste",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _run_translate(doc_id: int, force: bool = False):
    from tests.conftest import run_translate_sync
    run_translate_sync(doc_id, force=force)


class TestReadingE2E:
    """阅读全流程 API E2E（翻译 mock，不依赖 Google）"""

    @pytest.fixture(autouse=True)
    def _mocks(self, mock_translate):
        pass

    def test_full_reading_flow(self, client, wizard_story_text):
        """单会话全流程：导入 → 翻译 → 高亮/笔记/书签 → 搜索 → 生词 → 练习 → 进度 → 删除"""
        doc = _create_wizard_book(client, wizard_story_text)
        doc_id = doc["id"]
        _run_translate(doc_id)

        doc = client.get(f"/api/readings/{doc_id}").json()
        assert doc["translate_status"] == "done"
        blocks = client.get(f"/api/readings/{doc_id}/blocks").json()
        assert all(b.get("translation") for b in blocks)
        block = blocks[0]

        hl = client.post(f"/api/readings/{doc_id}/highlights", json={
            "block_id": block["id"],
            "start_offset": 0,
            "end_offset": min(10, len(block["text"])),
            "selected_text": block["text"][:10],
            "color": "yellow",
        }).json()
        note = client.post(f"/api/readings/{doc_id}/notes", json={
            "block_id": block["id"],
            "highlight_id": hl["id"],
            "content": "E2E test note",
        }).json()
        assert note["content"] == "E2E test note"

        bm = client.post(f"/api/readings/{doc_id}/bookmarks", json={
            "block_index": 2,
            "label": "Professor scene",
        }).json()
        assert bm["block_index"] == 2

        hits = client.get(f"/api/readings/{doc_id}/search", params={"q": "wizard"}).json()
        assert len(hits) >= 1

        sentence = "We have much to discuss, and a young wizard to protect."
        resp = client.post("/api/vocab/save", json={
            "word": "wizard",
            "source_platform": "reading",
            "source_video_id": f"reading-{doc_id}",
            "source_url": f"/reader?id={doc_id}",
            "source_title": doc["title"],
            "sentence": sentence,
            "sentence_translation": "【译】讨论",
        })
        assert resp.status_code == 200, resp.text
        saved = resp.json()
        assert saved.get("id") and saved["word"] == "wizard"

        stats = client.get(f"/api/readings/{doc_id}/vocab-words").json()
        assert stats["word_count"] >= 1 and "wizard" in stats["words"]

        ctx = client.get("/api/practice/context", params={
            "limit": 5,
            "source_video_id": f"reading-{doc_id}",
        }).json()
        assert len(ctx) >= 1, f"practice empty, saved={saved}"
        assert any(q["answer"].lower() == "wizard" for q in ctx)

        updated = client.patch(f"/api/readings/{doc_id}/progress", json={"block_index": 3}).json()
        assert updated["last_block_index"] == 3

        _run_translate(doc_id, force=True)
        assert client.get(f"/api/readings/{doc_id}").json()["translate_status"] == "done"

        r = client.delete(f"/api/readings/{doc_id}", params={"delete_vocab": True})
        assert r.status_code == 200
        assert client.get(f"/api/readings/{doc_id}").status_code == 404

    def test_import_split_chapters_only(self, client, wizard_story_text):
        doc = _create_wizard_book(client, wizard_story_text)
        assert doc["block_count"] >= 4
        assert doc["translate_status"] == "ready"

        blocks = client.get(f"/api/readings/{doc['id']}/blocks").json()
        assert len(blocks) == doc["block_count"]
        sections = {b["section_title"] for b in blocks if b.get("section_title")}
        assert any("Chapter One" in (s or "") for s in sections)
        assert any("Chapter Two" in (s or "") for s in sections)

    def test_reading_chapters_and_toc(self, client, wizard_story_text):
        doc = _create_wizard_book(client, wizard_story_text)
        doc_id = doc["id"]
        toc = client.get(f"/api/readings/{doc_id}/toc").json()
        assert toc["chapter_count"] >= 2
        assert len(toc["chapters"]) == toc["chapter_count"]
        assert toc["chapters"][0]["start_block"] == 0

        boot = client.get(f"/api/readings/{doc_id}/bootstrap").json()
        assert boot["chapters"]
        assert boot["chapter_index"] >= 0
        assert boot["blocks"]
        assert boot["chapter_block_total"] >= len(boot["blocks"])

        page = client.get(f"/api/readings/{doc_id}/chapters/1/blocks").json()
        assert page["chapter"]["chapter_index"] == 1
        assert page["items"]
        assert all(
            page["chapter"]["start_block"] <= item["order_index"] <= page["chapter"]["end_block"]
            for item in page["items"]
        )

    def test_translate_only(self, client, wizard_story_text):
        doc = _create_wizard_book(client, wizard_story_text)
        _run_translate(doc["id"])
        doc = client.get(f"/api/readings/{doc['id']}").json()
        assert doc["translate_status"] == "done"
        assert doc["translate_progress"] == 100
        assert doc["translated_blocks"] == doc["block_count"]

        blocks = client.get(f"/api/readings/{doc['id']}/blocks").json()
        assert all(b.get("translation") for b in blocks)


class TestReadingLiveTranslate:
    """真实有道翻译集成（慢，需国内网络）"""
    pytestmark = [pytest.mark.network, pytest.mark.integration]

    def test_real_translation(self, client, wizard_story_text):
        doc = _create_wizard_book(client, wizard_story_text, title="Live Translate E2E")
        _run_translate(doc["id"])
        doc = wait_until_translate_done(client, doc["id"], timeout=120)
        if doc.get("translate_status") != "done":
            pytest.skip(f"有道翻译不可用: {doc.get('status_message')}")
        blocks = client.get(f"/api/readings/{doc['id']}/blocks").json()
        translated = sum(1 for b in blocks if b.get("translation"))
        if translated < len(blocks) * 0.8:
            pytest.skip(f"有道翻译不完整，仅 {translated}/{len(blocks)} 段有译文")
        assert translated >= len(blocks) * 0.8


class TestHarryPotterEpub:
    """真实哈利波特 EPUB 上传测试（需本地文件 + 外网翻译）"""
    pytestmark = pytest.mark.network

    def test_harry_potter_epub_upload(self, client):
        if not os.getenv("TEST_HP_EPUB"):
            pytest.skip("设置 TEST_HP_EPUB=你的哈利波特.epub 路径")
        epub_path = Path(os.environ["TEST_HP_EPUB"])
        assert epub_path.exists(), f"文件不存在: {epub_path}"
        with epub_path.open("rb") as f:
            r = client.post(
                "/api/readings/upload",
                files={"file": (epub_path.name, f, "application/epub+zip")},
                data={"title": "Harry Potter E2E"},
            )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["block_count"] > 20, "哈利波特应切分出较多段落"
        assert doc["source_type"] == "epub"

        _run_translate(doc["id"])
        doc = wait_until_translate_done(client, doc["id"], timeout=300)
        assert doc.get("translate_status") == "done", doc.get("status_message")

        blocks = client.get(f"/api/readings/{doc['id']}/blocks").json()
        assert len(blocks) == doc["block_count"]
        ratio = sum(1 for b in blocks if b.get("translation")) / max(len(blocks), 1)
        assert ratio >= 0.85, f"翻译完成率过低: {ratio:.0%}"

        hits = client.get(f"/api/readings/{doc['id']}/search", params={"q": "Harry"}).json()
        assert len(hits) >= 1

        bm = client.post(f"/api/readings/{doc['id']}/bookmarks", json={
            "block_index": 0,
            "label": "Book start",
        }).json()
        assert bm["id"]

        print(f"\n[HP E2E] id={doc['id']} blocks={doc['block_count']} translated={ratio:.0%} search_hits={len(hits)}")
