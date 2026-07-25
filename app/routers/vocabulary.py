from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app import crud, models, schemas
from app import database
from app.services import dictionary, translator

router = APIRouter(tags=["vocabulary"])


@router.get("/api/word-lookup/{word}", response_model=schemas.WordRead)
def lookup_word_for_reader(word: str, session: Session = Depends(database.session_dependency)):
    """Click-to-translate: local ECDICT first, then Youdao if missing."""
    return dictionary.lookup_word_click(word, session=session)


@router.get("/api/word/{word}", response_model=schemas.WordRead)
def lookup_word(word: str, session: Session = Depends(database.session_dependency)):
    return dictionary.lookup_word_fast(word, session=session)


@router.get("/api/word-fast/{word}", response_model=schemas.WordRead)
def lookup_word_fast(word: str, session: Session = Depends(database.session_dependency)):
    return dictionary.lookup_word_fast(word, session=session)


@router.get("/api/word-enrich/{word}", response_model=schemas.WordRead)
def lookup_word_enrich(word: str, session: Session = Depends(database.session_dependency)):
    return dictionary.lookup_word_enrich(word, session=session)


@router.post("/api/vocab", response_model=schemas.VocabRead)
def add_vocab(request: schemas.VocabCreate, session: Session = Depends(database.session_dependency)):
    word_data = dictionary.lookup_word_fast(request.word)
    if request.wordbook_id:
        card = crud.save_vocab_with_context(
            session,
            {
                **word_data,
                "wordbook_id": request.wordbook_id,
                "source_platform": "wordbook",
                "source_video_id": f"wordbook-{request.wordbook_id}",
            },
        )
    else:
        card = crud.add_word_to_vocab(session, word_data)
    return crud.vocab_to_read(session, card)


@router.post("/api/vocab/save", response_model=schemas.VocabRead)
def save_vocab_from_extension(
    request: schemas.VocabSaveContext,
    session: Session = Depends(database.session_dependency),
):
    """插件收藏：带视频语境 + 自动查词"""
    word_data = dictionary.lookup_word_fast(request.word)
    payload = {
        **request.model_dump(),
        "definition": request.definition or word_data.get("definition", ""),
        "pronunciation": request.pronunciation or word_data.get("pronunciation"),
        "part_of_speech": request.part_of_speech or word_data.get("part_of_speech"),
        "translation": request.translation or word_data.get("translation"),
    }
    card = crud.save_vocab_with_context(session, payload)
    return crud.vocab_to_read(session, card)


@router.get("/api/vocab", response_model=list[schemas.VocabRead])
def list_vocab(
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    items = crud.list_vocab(session, source_video_id=source_video_id, wordbook_id=wordbook_id)
    return crud.vocab_to_read_many(session, items)


@router.get("/api/vocab/videos", response_model=list[schemas.VideoVocabSummary])
def list_vocab_videos(session: Session = Depends(database.session_dependency)):
    return crud.list_video_summaries(session)


@router.post("/api/translate/batch")
def translate_batch(request: schemas.TranslateBatchRequest):
    """插件批量翻译字幕"""
    results = translator.translate_batch(
        request.texts, source=request.source, target=request.target
    )
    return {"translations": results}


def _delete_vocab_card(session: Session, card: models.VocabItem) -> None:
    crud.delete_vocab_card(session, card)
    session.commit()


@router.delete("/api/vocab/{vocab_id}")
def delete_vocab(vocab_id: int, session: Session = Depends(database.session_dependency)):
    card = crud.get_vocab_card(session, vocab_id)
    if not card:
        raise HTTPException(status_code=404, detail="Vocabulary card not found")
    _delete_vocab_card(session, card)
    return {"ok": True}


@router.delete("/api/vocab/by-word/{word}")
def delete_vocab_by_word(word: str, session: Session = Depends(database.session_dependency)):
    """按单词取消收藏（用于词书刷词页星标取消）。"""
    card = crud.find_vocab_by_word(session, word)
    if not card:
        return {"ok": True, "removed": False}
    _delete_vocab_card(session, card)
    return {"ok": True, "removed": True}
