"""
GitHub 书库 E2E — 安徒生童话（GITenberg #66688）

验证：书库导入 → 章节/段落 → 懒翻译 → 阅读器 bootstrap → 搜索/书签 → 本地列表分离

用法:
  pytest tests/test_andersen_github_e2e.py -m network -v -s
"""
import pytest

from sqlmodel import Session, select

from app.models import LibraryBook, ReadingBlock, ReadingDocument
from tests.conftest import run_chapter_translate_sync

pytestmark = [pytest.mark.network, pytest.mark.integration]

BOOK_KEY = "andersen_fairy_tales_66688"
COMPLETE_KEY = "andersen_fairy_tales_complete_27200"


@pytest.fixture()
def mock_translate(monkeypatch):
    async def _fake(texts):
        return [f"【译】{t[:40]}" if t else "" for t in texts]

    monkeypatch.setattr(
        "app.services.reading_processor.translator.translate_reading_paragraphs",
        _fake,
    )


class TestAndersenGitHubE2E:
    """从 GitHub 导入安徒生童话，跑阅读模块主流程"""

    def test_github_import_and_reading_flow(self, client, test_engine, mock_translate):
        findings: list[str] = []

        # 1. 书库目录
        catalog = client.get("/api/readings/library/books").json()
        book = next((b for b in catalog if b["key"] == BOOK_KEY), None)
        assert book, "书库目录应包含安徒生童话"
        assert book["title"]
        findings.append(f"书库条目 OK：{book['title']} / {book.get('author','')}")

        # 2. GitHub 导入
        imp = client.post(f"/api/readings/library/books/{BOOK_KEY}/import")
        assert imp.status_code == 200, imp.text
        body = imp.json()
        assert body["ok"] is True
        doc = body["reading"]
        doc_id = doc["id"]
        assert doc["block_count"] > 50, "中篇童话应切分出较多段落"
        assert doc["translate_status"] == "ready", "懒翻译：导入后应立即可读"
        findings.append(f"导入 OK：{doc['block_count']} 段 / {doc.get('word_count', 0)} 词")

        # 3. 重复导入不重复建文档
        imp2 = client.post(f"/api/readings/library/books/{BOOK_KEY}/import")
        assert imp2.status_code == 200
        assert imp2.json()["created"] is False
        assert imp2.json()["reading"]["id"] == doc_id

        # 4. GitHub 书不在「本地导入」列表
        local = client.get("/api/readings?local=1").json()
        assert all(d["id"] != doc_id for d in local), "GitHub 书不应出现在本地导入区"

        # 5. 目录与 bootstrap
        toc = client.get(f"/api/readings/{doc_id}/toc").json()
        assert toc["chapter_count"] >= 1
        findings.append(f"章节数：{toc['chapter_count']}")

        boot = client.get(f"/api/readings/{doc_id}/bootstrap?limit=40").json()
        assert boot["doc"]["id"] == doc_id
        assert len(boot["blocks"]) > 0
        assert boot["has_more_blocks"] in (True, False)

        # 6. 懒翻译：只译第一章
        run_chapter_translate_sync(doc_id, boot["chapter_index"])

        with Session(test_engine) as db:
            ch0_end = toc["chapters"][boot["chapter_index"]]["end_block"]
            blocks = list(db.exec(
                select(ReadingBlock).where(ReadingBlock.document_id == doc_id)
            ).all())
            ch0 = [b for b in blocks if b.order_index <= ch0_end]
            ch_rest = [b for b in blocks if b.order_index > ch0_end]
            ch0_translated = sum(1 for b in ch0 if (b.translation or "").strip())
            rest_translated = sum(1 for b in ch_rest if (b.translation or "").strip())
            findings.append(
                f"懒翻译：第1章 {ch0_translated}/{len(ch0)} 段有译文，其余章 {rest_translated}/{len(ch_rest)}"
            )
        assert ch0_translated >= max(1, int(len(ch0) * 0.8))

        # 7. 搜索 / 书签 / 进度
        hits = client.get(f"/api/readings/{doc_id}/search", params={"q": "duckling"}).json()
        findings.append(f"搜索 duckling：{len(hits)} 条")

        bm = client.post(f"/api/readings/{doc_id}/bookmarks", json={
            "block_index": boot["blocks"][0]["order_index"],
            "label": "E2E start",
        }).json()
        assert bm["id"]

        prog = client.patch(f"/api/readings/{doc_id}/progress", json={
            "block_index": boot["blocks"][0]["order_index"],
        }).json()
        assert prog["last_block_index"] == boot["blocks"][0]["order_index"]

        # 8. 补译 API
        fill = client.post(f"/api/readings/{doc_id}/translate").json()
        assert fill["ok"] is True

        # 输出 E2E 摘要（便于人工查看薄弱点）
        print("\n=== 安徒生童话 GitHub E2E 摘要 ===")
        for line in findings:
            print(" -", line)

        # 记录薄弱点断言（当前已知限制）
        assert doc["block_count"] < 5000, "段落数应在可接受范围"
        if toc["chapter_count"] <= 2:
            findings.append("薄弱：章节识别偏少，可能整本书只有1~2章")

    def test_complete_andersen_not_rejected(self, client, test_engine, mock_translate):
        """Gutenberg #27200 超长篇全集应能成功导入"""
        imp = client.post(f"/api/readings/library/books/{COMPLETE_KEY}/import")
        assert imp.status_code == 200, imp.text
        doc = imp.json()["reading"]
        assert doc["block_count"] > 1000
        assert doc["translate_status"] == "ready"
        toc = client.get(f"/api/readings/{doc['id']}/toc").json()
        assert toc["chapter_count"] >= 1
        # 章节不应大量 1 段章
        tiny = sum(1 for ch in toc["chapters"] if ch["block_count"] < 3)
        assert tiny < len(toc["chapters"]) * 0.5
