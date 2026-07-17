"""章节平衡与搜索优化测试"""
from app.models import ReadingBlock
from app.services.reading_chapters import derive_chapter_specs
from app.services.reading_limits import MIN_CHAPTER_BLOCKS, MAX_CHAPTER_BLOCKS


def test_balance_merges_tiny_chapters():
    blocks = []
    idx = 0
    titles = ["A", "A", "B", "B", "C"] + ["C"] * (MIN_CHAPTER_BLOCKS + 2)
    for title in titles:
        blocks.append(
            ReadingBlock(
                id=idx + 1,
                document_id=1,
                order_index=idx,
                text=f"Paragraph {idx} with enough English words here.",
                section_title=title,
            )
        )
        idx += 1
    specs = derive_chapter_specs(blocks)
    assert specs
    assert all(s["block_count"] >= 2 or s == specs[-1] for s in specs)


def test_search_uses_fts(client, test_engine):
    doc = client.post("/api/readings", json={
        "title": "Search test",
        "content": "The ugly duckling swam alone.\n\nLater he became a swan.",
    }).json()
    hits = client.get(f"/api/readings/{doc['id']}/search", params={"q": "duckling"}).json()
    assert len(hits) >= 1
