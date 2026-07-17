from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app import crud, database, schemas

router = APIRouter(prefix="/api", tags=["review"])


@router.post("/review", response_model=schemas.VocabRead)
def review_vocab(request: schemas.ReviewRequest, session: Session = Depends(database.session_dependency)):
    card = crud.review_vocab(session, request.vocab_id, request.rating)
    if not card:
        raise HTTPException(status_code=404, detail="Vocabulary card not found")
    return crud.vocab_to_read(session, card)


@router.get("/recommendations", response_model=list[schemas.VocabRead])
def recommendations(
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    items = crud.get_due_vocab(
        session,
        datetime.utcnow(),
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
    )
    return [crud.vocab_to_read(session, item) for item in items]
