"""Debug practice empty after cache tests"""
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

import app.database as db
import app.services.reading_processor as rp
from app.services import reading_cache

FIXTURES = Path(__file__).parent / "fixtures"
text = (FIXTURES / "wizard_story.txt").read_text(encoding="utf-8")


def make_client(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 't.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    db.engine = engine
    rp.engine = engine

    def _gs():
        with Session(engine) as s:
            yield s

    from app.main import app
    from app.database import get_session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = _gs
    return TestClient(app, raise_server_exceptions=True), engine


async def fake_translate(texts):
    return [f"【译】{t[:48]}" if t else "" for t in texts]


def main():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        c1, _ = make_client(base / "t1")
        reading_cache.clear_all()
        r = c1.post(
            "/api/readings",
            json={"title": "B", "content": text, "source_type": "paste"},
        )
        c1.get(f"/api/readings/{r.json()['id']}/bootstrap?limit=5")
        c1.close()
        reading_cache.clear_all()

        c3, e3 = make_client(base / "t3")
        reading_cache.clear_all()
        with Session(e3) as s:
            from app import crud

            crud.save_translation_cache(s, "Hello unique cache test.", "你好")
            s.commit()
        c3.close()
        reading_cache.clear_all()

        c4, e4 = make_client(base / "t4")
        reading_cache.clear_all()
        rp.translator.translate_reading_paragraphs = fake_translate
        from app.routers.readings import _start_translate

        # noqa - patch no-op
        import app.routers.readings as rr

        rr._start_translate = lambda doc_id: None

        doc = c4.post(
            "/api/readings",
            json={"title": "W", "content": text, "source_type": "paste"},
        ).json()
        from tests.conftest import run_translate_sync

        run_translate_sync(doc["id"])
        doc_id = doc["id"]
        sentence = "We have much to discuss, and a young wizard to protect."
        saved = c4.post(
            "/api/vocab/save",
            json={
                "word": "wizard",
                "source_platform": "reading",
                "source_video_id": f"reading-{doc_id}",
                "source_url": f"/reader?id={doc_id}",
                "source_title": doc["title"],
                "sentence": sentence,
                "sentence_translation": "x",
            },
        ).json()
        ctx = c4.get(
            "/api/practice/context",
            params={"limit": 5, "source_video_id": f"reading-{doc_id}"},
        ).json()
        print("saved sentence:", saved.get("sentence"))
        print("ctx len:", len(ctx))
        with Session(e4) as s:
            from app import crud

            cards = crud.get_all_vocab_for_practice(
                s, limit=15, source_video_id=f"reading-{doc_id}"
            )
            for c in cards:
                print("card", c.word, repr(c.sentence))
        c4.close()


if __name__ == "__main__":
    main()
