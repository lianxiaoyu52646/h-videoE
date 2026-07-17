import random
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app import crud, database, schemas

router = APIRouter(prefix="/api/practice", tags=["practice"])


@router.get("/spelling", response_model=list[schemas.PracticeQuestion])
def get_spelling_questions(
    session: Session = Depends(database.session_dependency),
    limit: int = 10,
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
):
    """默写练习：看中文释义，拼写英文单词"""
    cards = crud.get_all_vocab_for_practice(
        session,
        limit=limit,
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
    )
    questions = []
    for card in cards:
        questions.append(schemas.PracticeQuestion(
            type="spelling",
            definition=card.definition,
            pronunciation=card.pronunciation,
            question=f"请根据释义拼写单词：{card.definition}",
            answer=card.word,
        ))
    return questions


@router.get("/listening", response_model=list[schemas.PracticeQuestion])
def get_listening_questions(
    session: Session = Depends(database.session_dependency),
    limit: int = 10,
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
):
    """听力练习：TTS 朗读单词，用户拼写"""
    cards = crud.get_all_vocab_for_practice(
        session,
        limit=limit,
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
    )
    questions = []
    for card in cards:
        questions.append(schemas.PracticeQuestion(
            type="listening",
            word=card.word,
            question="请听录音并拼写单词",
            answer=card.word,
        ))
    return questions


@router.get("/context", response_model=list[schemas.PracticeQuestion])
def get_context_questions(
    session: Session = Depends(database.session_dependency),
    limit: int = 10,
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
):
    """语境填空：根据收藏时的原句填词（阅读/视频生词）"""
    import re

    cards = crud.get_all_vocab_for_practice(
        session,
        limit=limit * 3,
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
    )
    questions = []
    for card in cards:
        if not card.sentence or not card.word:
            continue
        word = card.word.strip()
        pattern = re.compile(re.escape(word), re.I)
        if pattern.search(card.sentence):
            blank = pattern.sub("______", card.sentence, count=1)
        else:
            blank = f"{card.sentence}\n\n请根据这段语境回忆目标单词。"
        questions.append(schemas.PracticeQuestion(
            type="context",
            word=card.word,
            definition=card.definition,
            question=blank,
            answer=word,
            choices=None,
        ))
        if len(questions) >= limit:
            break
    return questions


@router.get("/reading", response_model=list[schemas.PracticeQuestion])
def get_reading_questions(
    session: Session = Depends(database.session_dependency),
    limit: int = 5,
    source_video_id: str | None = Query(None),
    wordbook_id: int | None = Query(None),
):
    """阅读练习：看释义选单词（选择题）"""
    cards = crud.get_all_vocab_for_practice(
        session,
        limit=limit * 4,
        source_video_id=source_video_id,
        wordbook_id=wordbook_id,
    )
    if len(cards) < 4:
        return []
    questions = []
    for i in range(min(limit, len(cards) // 4)):
        sample = random.sample(list(cards), 4)
        correct = sample[0]
        choices = [c.word for c in sample]
        random.shuffle(choices)
        questions.append(schemas.PracticeQuestion(
            type="reading",
            definition=correct.definition,
            question=f"选择与释义匹配的单词：{correct.definition}",
            answer=correct.word,
            choices=choices,
        ))
    return questions
