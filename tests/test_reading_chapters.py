from app import crud, database, models
from app.services.reading_chapters import derive_chapter_specs
from sqlmodel import Session


def test_derive_chapter_specs_groups_by_section_title():
    blocks = [
        models.ReadingBlock(document_id=1, order_index=0, text="a", section_title=None),
        models.ReadingBlock(document_id=1, order_index=1, text="b", section_title="Chapter One"),
        models.ReadingBlock(document_id=1, order_index=2, text="c", section_title="Chapter One"),
        models.ReadingBlock(document_id=1, order_index=3, text="d", section_title="Chapter Two"),
    ]
    specs = derive_chapter_specs(blocks)
    assert len(specs) == 3
    assert specs[0]["title"] == "开篇"
    assert specs[1]["title"] == "Chapter One"
    assert specs[1]["block_count"] == 2
    assert specs[2]["title"] == "Chapter Two"


def test_rebuild_reading_chapters_persists_rows():
    database.init_db()
    with Session(database.engine) as session:
        doc = crud.create_reading(
            session,
            "Chapter Book",
            "Intro line.\n\nChapter One\n\nFirst paragraph.\n\nSecond paragraph.\n\nChapter Two\n\nThird paragraph.",
        )
        chapters = crud.list_reading_chapters(session, doc.id)
        assert len(chapters) >= 2
        assert chapters[0].start_block == 0
