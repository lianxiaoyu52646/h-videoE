#!/usr/bin/env python3
"""
阅读模块全方位 E2E — 哈利波特 EPUB 或魔法题材样章 + 真实有道翻译

用法:
  # 终端1：启动服务
  uvicorn app.main:app --host 127.0.0.1 --port 8000

  # 终端2：样章全功能测试
  python scripts/e2e_reading_test.py

  # 哈利波特 EPUB
  set TEST_HP_EPUB=D:\\books\\Harry_Potter_1.epub
  python scripts/e2e_reading_test.py --epub %TEST_HP_EPUB%
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "wizard_story.txt"
DEFAULT_BASE = "http://127.0.0.1:8000"


def ok(msg: str):
    print(f"  [OK] {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")
    return False


def wait_translate(client: httpx.Client, base: str, doc_id: int, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    last_prog = -1
    while time.time() < deadline:
        doc = client.get(f"{base}/api/readings/{doc_id}").json()
        st = doc.get("translate_status")
        prog = doc.get("translate_progress", 0)
        if prog != last_prog and st == "translating":
            print(f"     翻译进度 {prog}% …")
            last_prog = prog
        if st in ("done", "failed"):
            return doc
        time.sleep(1)
    return doc


def run_e2e(base: str, epub: Path | None, skip_network: bool) -> int:
    print(f"\n[E2E] 哈利波特阅读模块全方位测试 @ {base}\n")
    errors = 0
    passed = 0
    results: list[str] = []

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal errors, passed
        if cond:
            passed += 1
            ok(f"{name}" + (f" — {detail}" if detail else ""))
            results.append(f"PASS {name}")
        else:
            errors += 1
            fail(f"{name}" + (f" — {detail}" if detail else ""))
            results.append(f"FAIL {name}")

    with httpx.Client(timeout=120) as client:
        try:
            client.get(f"{base}/read")
            check("服务可达", True, "/read")
        except Exception as e:
            print(f"  [FAIL] 无法连接 {base}: {e}")
            return 1

        if not skip_network:
            try:
                w = client.get(f"{base}/api/word/wizard").json()
                tr = w.get("youdao_translation") or w.get("translation")
                check("有道查词", bool(tr), str(tr)[:30] if tr else "")
            except Exception as e:
                check("有道查词", False, str(e))
        else:
            print("  [SKIP] 跳过联网查词")

        if epub and epub.exists():
            print(f"\n[EPUB] 上传哈利波特 EPUB: {epub.name}")
            with epub.open("rb") as f:
                r = client.post(
                    f"{base}/api/readings/upload",
                    files={"file": (epub.name, f, "application/epub+zip")},
                    data={"title": "Harry Potter E2E"},
                )
            if r.status_code != 200:
                check("EPUB 上传", False, r.text[:120])
                return 1
            doc = r.json()
            is_epub = True
            search_q = "Harry"
            vocab_word = "potter"
            check("EPUB 导入", True, f"id={doc['id']} blocks={doc['block_count']}")
        else:
            print("\n[BOOK] 使用魔法题材样章（哈利波特风格）")
            text = FIXTURE.read_text(encoding="utf-8")
            r = client.post(f"{base}/api/readings", json={
                "title": "Harry Potter Style E2E",
                "content": text,
            })
            if r.status_code != 200:
                check("样章导入", False, r.text[:120])
                return 1
            doc = r.json()
            is_epub = False
            search_q = "wizard"
            vocab_word = "wizard"
            check("样章导入", True, f"id={doc['id']} blocks={doc['block_count']}")

        doc_id = doc["id"]
        timeout = 900 if is_epub else 180

        shelf = client.get(f"{base}/api/readings").json()
        check("书架列表", any(d["id"] == doc_id for d in shelf), f"{len(shelf)} 本")

        if doc.get("translate_status") not in ("done", "translating"):
            client.post(f"{base}/api/readings/{doc_id}/translate")

        print("  [WAIT] 等待有道翻译…")
        doc = wait_translate(client, base, doc_id, timeout=timeout)
        check("全书翻译", doc.get("translate_status") == "done", doc.get("status_message", ""))

        blocks = client.get(f"{base}/api/readings/{doc_id}/blocks").json()
        ratio = sum(1 for b in blocks if b.get("translation")) / max(len(blocks), 1)
        check("译文覆盖率", ratio >= (0.85 if is_epub else 0.8), f"{ratio:.0%}")

        if blocks and blocks[0].get("translation"):
            tr0 = blocks[0]["translation"]
            check("首段中文译文", any("\u4e00" <= c <= "\u9fff" for c in tr0), tr0[:36] + "…")
        else:
            check("首段中文译文", False)

        hits = client.get(f"{base}/api/readings/{doc_id}/search", params={"q": search_q}).json()
        check("文内搜索", len(hits) >= 1, f"'{search_q}' → {len(hits)} 条")

        b0 = blocks[0]
        block_for_vocab = next(
            (b for b in blocks if vocab_word.lower() in b["text"].lower()),
            b0,
        )
        hl = client.post(f"{base}/api/readings/{doc_id}/highlights", json={
            "block_id": b0["id"],
            "start_offset": 0,
            "end_offset": min(8, len(b0["text"])),
            "selected_text": b0["text"][:8],
            "color": "green",
        }).json()
        check("高亮", hl.get("id") is not None, f"id={hl.get('id')}")

        note = client.post(f"{base}/api/readings/{doc_id}/notes", json={
            "block_id": b0["id"],
            "highlight_id": hl["id"],
            "content": "HP E2E note",
        }).json()
        check("笔记", note.get("id") is not None)

        note2 = client.patch(
            f"{base}/api/readings/{doc_id}/notes/{note['id']}",
            json={"content": "HP E2E updated"},
        ).json()
        check("编辑笔记", note2.get("content") == "HP E2E updated")

        bm = client.post(f"{base}/api/readings/{doc_id}/bookmarks", json={
            "block_index": min(2, len(blocks) - 1),
            "label": "HP bookmark",
        }).json()
        check("书签", bm.get("id") is not None)

        bm2 = client.patch(
            f"{base}/api/readings/{doc_id}/bookmarks/{bm['id']}",
            json={"label": "HP updated"},
        ).json()
        check("编辑书签", bm2.get("label") == "HP updated")

        client.patch(f"{base}/api/readings/{doc_id}/progress", json={"block_index": 1})
        check("阅读进度", True)

        saved = client.post(f"{base}/api/vocab/save", json={
            "word": vocab_word,
            "source_platform": "reading",
            "source_video_id": f"reading-{doc_id}",
            "source_url": f"/reader?id={doc_id}",
            "source_title": doc["title"],
            "sentence": block_for_vocab["text"],
            "sentence_translation": block_for_vocab.get("translation") or "",
        })
        check("生词收藏", saved.status_code == 200, vocab_word)

        stats = client.get(f"{base}/api/readings/{doc_id}/vocab-words").json()
        check("生词统计", vocab_word in stats.get("words", []), f"{stats.get('word_count')} 词")

        practice = client.get(f"{base}/api/practice/context", params={
            "limit": 5,
            "source_video_id": f"reading-{doc_id}",
        }).json()
        check("语境练习", any(q.get("answer", "").lower() == vocab_word for q in practice), f"{len(practice)} 题")

        client.post(f"{base}/api/readings/{doc_id}/translate")
        print("  [WAIT] 重译验证…")
        doc_re = wait_translate(client, base, doc_id, timeout=timeout)
        check("强制重译", doc_re.get("translate_status") == "done")

        client.delete(f"{base}/api/readings/{doc_id}/highlights/{hl['id']}")
        client.delete(f"{base}/api/readings/{doc_id}/notes/{note['id']}")
        client.delete(f"{base}/api/readings/{doc_id}/bookmarks/{bm['id']}")
        check("清理高亮/笔记/书签", True)

        r = client.delete(f"{base}/api/readings/{doc_id}", params={"delete_vocab": True})
        check("删除书籍", r.status_code == 200)

        print(f"\n{'='*48}")
        print(f"结果: {passed} 通过 / {passed + errors} 项")
        if errors:
            print(f"[FAIL] E2E 完成，{errors} 项失败")
            return 1
        print(f"[PASS] 哈利波特阅读 E2E 全部通过")
        print(f"   来源: {'EPUB' if is_epub else '魔法样章'}")
        return 0


def main():
    p = argparse.ArgumentParser(description="哈利波特阅读模块全方位 E2E")
    p.add_argument("--base", default=DEFAULT_BASE)
    p.add_argument("--epub", type=Path, default=None, help="哈利波特 EPUB 路径")
    p.add_argument("--skip-network", action="store_true")
    args = p.parse_args()
    epub = args.epub or (Path(os.environ["TEST_HP_EPUB"]) if os.environ.get("TEST_HP_EPUB") else None)
    sys.exit(run_e2e(args.base, epub, args.skip_network))


if __name__ == "__main__":
    main()
