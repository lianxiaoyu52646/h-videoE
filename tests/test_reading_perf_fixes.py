"""阅读模块 P0/P1 优化回归测试"""
from sqlmodel import Session, select

from app import models
from app.services.reading_chapters import derive_chapter_specs
from app.services.text_splitter import split_into_blocks


def test_count_translated_blocks_sql(client, test_engine):
    doc = client.post("/api/readings", json={
        "title": "Count test",
        "content": "Alpha one.\n\nBeta two.\n\nGamma three.",
    }).json()
    with Session(test_engine) as db:
        blocks = list(db.exec(
            select(models.ReadingBlock).where(models.ReadingBlock.document_id == doc["id"])
        ).all())
        blocks[0].translation = "甲"
        blocks[2].translation = "   "  # 空白不算已译
        db.add(blocks[0])
        db.add(blocks[2])
        db.commit()

        from app import crud

        assert crud.count_translated_blocks(db, doc["id"]) == 1
        assert crud.sync_translated_blocks(db, doc["id"]) == 1
        db.commit()
        assert crud.increment_translated_blocks(db, doc["id"], 1) == 2
        db.commit()
        doc_row = db.get(models.ReadingDocument, doc["id"])
        assert doc_row.translated_blocks == 2
        assert crud.count_translated_blocks(db, doc["id"]) == 1


def test_vocab_stats_no_global_fallback(client, test_engine):
    """本书无生词时不应混入全库生词"""
    doc = client.post("/api/readings", json={
        "title": "Vocab scope",
        "content": "Hello world paragraph.",
    }).json()
    # 先在其他 source 存一个生词
    client.post("/api/vocab/save", json={
        "word": "otherword",
        "source_video_id": "video-999",
        "source_title": "Other",
    })
    stats = client.get(f"/api/readings/{doc['id']}/vocab-words").json()
    assert stats["word_count"] == 0
    assert "otherword" not in stats["words"]


def test_gutenberg_section_markers_create_chapters():
    text = """THE UGLY DUCKLING

It was lovely summer weather in the country.

CHAPTER II

The duckling grew larger."""
    blocks = split_into_blocks(text)
    titles = {b["section_title"] for b in blocks if b.get("section_title")}
    assert "THE UGLY DUCKLING" in titles or any("UGLY DUCKLING" in (t or "") for t in titles)
    specs = derive_chapter_specs([
        models.ReadingBlock(
            id=i + 1,
            document_id=1,
            order_index=i,
            text=b["text"],
            section_title=b.get("section_title"),
        )
        for i, b in enumerate(blocks)
    ])
    assert len(specs) >= 2


def test_bootstrap_lazy_annotations(client, wizard_story_text):
    doc_id = client.post("/api/readings", json={
        "title": "Lazy boot",
        "content": wizard_story_text,
    }).json()["id"]
    boot = client.get(f"/api/readings/{doc_id}/bootstrap?limit=5").json()
    assert boot["blocks"]
    assert boot["highlights"] == []
    assert boot["notes"] == []
    assert boot["bookmarks"] == []

    client.post(f"/api/readings/{doc_id}/bookmarks", json={"block_index": 0, "label": "start"})
    marks = client.get(f"/api/readings/{doc_id}/bookmarks").json()
    assert len(marks) == 1


def test_notes_include_block_index(client, wizard_story_text):
    doc_id = client.post("/api/readings", json={
        "title": "Note jump",
        "content": wizard_story_text,
    }).json()["id"]
    blocks = client.get(f"/api/readings/{doc_id}/blocks?offset=0&limit=5").json()["items"]
    note = client.post(f"/api/readings/{doc_id}/notes", json={
        "block_id": blocks[0]["id"],
        "content": "test note",
    }).json()
    listed = client.get(f"/api/readings/{doc_id}/notes").json()
    assert listed[0]["block_index"] == blocks[0]["order_index"]
    assert note["id"]

