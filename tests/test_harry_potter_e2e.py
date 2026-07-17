"""
哈利波特阅读模块全方位 E2E — 真实有道翻译 + 全 API 覆盖

用法:
  # 魔法题材样章（内置，无需 EPUB）
  pytest tests/test_harry_potter_e2e.py -m network -v -s

  # 真实哈利波特 EPUB
  set TEST_HP_EPUB=D:\\books\\Harry_Potter_1.epub
  pytest tests/test_harry_potter_e2e.py -m network -v -s
"""
import os
from pathlib import Path

import pytest

from tests.conftest import FIXTURES, run_translate_sync, wait_until_translate_done

pytestmark = [pytest.mark.network, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _no_background_translate(monkeypatch):
    monkeypatch.setattr("app.routers.readings._start_translate", lambda doc_id: None)


def _run_translate(doc_id: int, force: bool = False):
    run_translate_sync(doc_id, force=force)


def _import_hp_book(client, wizard_story_text: str) -> tuple[dict, bool]:
    """返回 (doc_json, is_epub)"""
    epub_path = os.getenv("TEST_HP_EPUB")
    if epub_path and Path(epub_path).exists():
        with Path(epub_path).open("rb") as f:
            r = client.post(
                "/api/readings/upload",
                files={"file": (Path(epub_path).name, f, "application/epub+zip")},
                data={"title": "Harry Potter E2E"},
            )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["source_type"] == "epub"
        assert doc["block_count"] > 20, "哈利波特 EPUB 应切分出较多段落"
        return doc, True

    r = client.post("/api/readings", json={
        "title": "Harry Potter Style E2E",
        "content": wizard_story_text,
        "source_type": "paste",
    })
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["block_count"] >= 4
    return doc, False


def _read_sse_events(client, doc_id: int, max_events: int = 5) -> list[str]:
    """读取 SSE 事件（翻译完成后流会立即结束）"""
    resp = client.get(f"/api/readings/{doc_id}/stream")
    assert resp.status_code == 200
    events = []
    for part in resp.text.split("\n\n"):
        part = part.strip()
        if part and not part.startswith(":"):
            events.append(part)
        if len(events) >= max_events:
            break
    return events


class TestHarryPotterFullE2E:
    """哈利波特 / 魔法题材 — 阅读模块全方位功能验证"""

    def test_hp_reading_full_flow(self, client, wizard_story_text):
        results: list[str] = []

        def record(name: str, ok: bool, detail: str = ""):
            mark = "PASS" if ok else "FAIL"
            msg = f"[{mark}] {name}" + (f" — {detail}" if detail else "")
            results.append(msg)
            assert ok, msg

        # ── 0. 查词（有道） ──
        word = client.get("/api/word/wizard").json()
        record(
            "有道查词 wizard",
            bool(word.get("youdao_translation") or word.get("translation")),
            word.get("youdao_translation") or word.get("translation") or "",
        )

        # ── 1. 导入 ──
        doc, is_epub = _import_hp_book(client, wizard_story_text)
        doc_id = doc["id"]
        record(
            "EPUB/样章导入",
            doc_id > 0,
            f"id={doc_id} blocks={doc['block_count']} type={doc.get('source_type')}",
        )

        # ── 2. 书架列表 ──
        shelf = client.get("/api/readings").json()
        record("书架列表", any(d["id"] == doc_id for d in shelf), f"共 {len(shelf)} 本")

        # ── 3. 翻译（真实有道） ──
        _run_translate(doc_id)
        doc = client.get(f"/api/readings/{doc_id}").json()
        record(
            "全书翻译",
            doc.get("translate_status") == "done",
            doc.get("status_message") or doc.get("translate_status"),
        )

        blocks = client.get(f"/api/readings/{doc_id}/blocks").json()
        record("段落加载", len(blocks) == doc["block_count"], f"{len(blocks)} 段")

        translated = sum(1 for b in blocks if (b.get("translation") or "").strip())
        ratio = translated / max(len(blocks), 1)
        min_ratio = 0.85 if is_epub else 0.8
        record("译文覆盖率", ratio >= min_ratio, f"{translated}/{len(blocks)} = {ratio:.0%}")

        sample = next((b for b in blocks if b.get("translation")), blocks[0])
        has_zh = any("\u4e00" <= c <= "\u9fff" for c in (sample.get("translation") or ""))
        record("译文含中文", has_zh, (sample.get("translation") or "")[:40])

        # ── 4. SSE 推送 ──
        sse = _read_sse_events(client, doc_id, max_events=3)
        record("SSE 流", len(sse) >= 1, f"{len(sse)} 个事件")

        # ── 5. 文内搜索 ──
        queries = ["Harry", "wizard", "Professor"] if is_epub else ["wizard", "Professor", "Pember"]
        search_ok = False
        for q in queries:
            hits = client.get(f"/api/readings/{doc_id}/search", params={"q": q}).json()
            if hits:
                search_ok = True
                record("文内搜索", True, f"'{q}' → {len(hits)} 条")
                break
        if not search_ok:
            record("文内搜索", False, f"尝试 {queries}")

        # ── 6. 高亮 + 笔记 ──
        block = blocks[min(1, len(blocks) - 1)]
        hl = client.post(f"/api/readings/{doc_id}/highlights", json={
            "block_id": block["id"],
            "start_offset": 0,
            "end_offset": min(12, len(block["text"])),
            "selected_text": block["text"][:12],
            "color": "yellow",
        }).json()
        record("创建高亮", hl.get("id") is not None, f"id={hl.get('id')}")

        hls = client.get(f"/api/readings/{doc_id}/highlights").json()
        record("高亮列表", any(h["id"] == hl["id"] for h in hls), f"{len(hls)} 条")

        note = client.post(f"/api/readings/{doc_id}/notes", json={
            "block_id": block["id"],
            "highlight_id": hl["id"],
            "content": "HP E2E: young wizard note",
        }).json()
        record("创建笔记", note.get("content") == "HP E2E: young wizard note")

        note2 = client.patch(
            f"/api/readings/{doc_id}/notes/{note['id']}",
            json={"content": "HP E2E: updated note"},
        ).json()
        record("编辑笔记", note2.get("content") == "HP E2E: updated note")

        notes = client.get(f"/api/readings/{doc_id}/notes").json()
        record("笔记列表", len(notes) >= 1)

        # ── 7. 书签 ──
        bm = client.post(f"/api/readings/{doc_id}/bookmarks", json={
            "block_index": min(2, len(blocks) - 1),
            "label": "Chapter start",
        }).json()
        record("创建书签", bm.get("id") is not None)

        bm2 = client.patch(
            f"/api/readings/{doc_id}/bookmarks/{bm['id']}",
            json={"label": "HP bookmark updated"},
        ).json()
        record("编辑书签", bm2.get("label") == "HP bookmark updated")

        bms = client.get(f"/api/readings/{doc_id}/bookmarks").json()
        record("书签列表", len(bms) >= 1)

        # ── 8. 进度 ──
        prog = client.patch(
            f"/api/readings/{doc_id}/progress",
            json={"block_index": min(3, len(blocks) - 1)},
        ).json()
        record("阅读进度", prog.get("last_block_index") == min(3, len(blocks) - 1))

        # ── 9. 生词 + 练习 ──
        vocab_word = "potter" if is_epub else "wizard"
        vocab_block = next(
            (b for b in blocks if vocab_word.lower() in b["text"].lower()),
            block,
        )
        sentence = vocab_block["text"][:120]
        saved = client.post("/api/vocab/save", json={
            "word": vocab_word,
            "source_platform": "reading",
            "source_video_id": f"reading-{doc_id}",
            "source_url": f"/reader?id={doc_id}",
            "source_title": doc["title"],
            "sentence": sentence,
            "sentence_translation": vocab_block.get("translation") or "",
        })
        record("生词收藏", saved.status_code == 200, saved.json().get("word", ""))

        stats = client.get(f"/api/readings/{doc_id}/vocab-words").json()
        record(
            "书籍生词统计",
            stats.get("word_count", 0) >= 1 and vocab_word in stats.get("words", []),
            f"{stats.get('word_count')} 词",
        )

        practice = client.get("/api/practice/context", params={
            "limit": 5,
            "source_video_id": f"reading-{doc_id}",
        }).json()
        record(
            "语境练习",
            any(q.get("answer", "").lower() == vocab_word for q in practice),
            f"{len(practice)} 题",
        )

        # ── 10. 重译 ──
        _run_translate(doc_id, force=True)
        doc_re = client.get(f"/api/readings/{doc_id}").json()
        record("强制重译", doc_re.get("translate_status") == "done")

        # ── 11. 修改标题 ──
        renamed = client.patch(f"/api/readings/{doc_id}", json={
            "title": "Harry Potter E2E Done",
        }).json()
        record("修改书名", renamed.get("title") == "Harry Potter E2E Done")

        # ── 12. 清理（高亮/笔记/书签/书籍） ──
        client.delete(f"/api/readings/{doc_id}/highlights/{hl['id']}")
        record("删除高亮", client.get(f"/api/readings/{doc_id}/highlights").json() == [])

        client.delete(f"/api/readings/{doc_id}/notes/{note['id']}")
        record("删除笔记", len(client.get(f"/api/readings/{doc_id}/notes").json()) == 0)

        client.delete(f"/api/readings/{doc_id}/bookmarks/{bm['id']}")
        record("删除书签", len(client.get(f"/api/readings/{doc_id}/bookmarks").json()) == 0)

        r = client.delete(f"/api/readings/{doc_id}", params={"delete_vocab": True})
        record("删除书籍", r.status_code == 200 and client.get(f"/api/readings/{doc_id}").status_code == 404)

        print("\n" + "=" * 50)
        print("哈利波特阅读模块 E2E 报告")
        print("=" * 50)
        for line in results:
            print(line)
        print("=" * 50)
        print(f"合计: {len(results)} 项, 来源: {'EPUB' if is_epub else '魔法样章'}")
