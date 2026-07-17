"""英文阅读 API — 文档库 + 双语段落 + 点词收藏"""
import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app import crud, database, schemas, models
from app.config import settings
from app.models import ReadingDocument
from app.services import book_library
from app.services import reading_processor
from app.services import reading_cache
from app.services.file_parser import parse_upload

router = APIRouter(prefix="/api/readings", tags=["readings"])

from app.services.reading_limits import MAX_CONTENT_CHARS, MAX_UPLOAD_BYTES

_sse_subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)


def _sse_publish(doc_id: int, event: str, data: dict):
    for queue in _sse_subscribers.get(doc_id, []):
        try:
            queue.put_nowait((event, data))
        except asyncio.QueueFull:
            pass


reading_processor.set_sse_publisher(_sse_publish)


def _enrich_library_book(session: Session, book: models.LibraryBook) -> schemas.LibraryBookRead:
    data = schemas.LibraryBookRead.model_validate(book).model_dump()
    if book.reading_document_id:
        doc = crud.get_reading(session, book.reading_document_id)
        if doc:
            data.update(
                {
                    "reading_translate_status": doc.translate_status,
                    "reading_translate_progress": doc.translate_progress,
                    "reading_translated_blocks": doc.translated_blocks,
                    "reading_block_count": doc.block_count,
                    "reading_read_progress": doc.read_progress,
                    "reading_status_message": doc.status_message or "",
                }
            )
    return schemas.LibraryBookRead(**data)


def _create_translate_job(
    doc_id: int,
    *,
    force: bool = False,
    chapter_index: int | None = None,
    prefetch_next: bool = False,
):
    with Session(database.engine) as session:
        doc = crud.get_reading(session, doc_id)
        if not doc:
            return None
        payload: dict = {"doc_id": doc_id, "force": force, "mode": "full"}
        if chapter_index is not None:
            payload.update({
                "mode": "chapter",
                "chapter_index": chapter_index,
                "prefetch_next": prefetch_next,
            })
        elif not force:
            payload["mode"] = "fill_missing"
        job = crud.create_job(
            session,
            "reading_translate",
            target_type="reading",
            target_id=doc_id,
            payload=payload,
            user_id=doc.user_id,
        )
        doc.active_job_id = job.id
        session.add(doc)
        session.commit()
        return job.id


def _start_translate(doc_id: int, force: bool = False):
    job_id = _create_translate_job(doc_id, force=force)
    if not job_id or not settings.inline_worker:
        return
    reading_processor.start_translation(doc_id, force=force, job_id=job_id)


def _start_chapter_translate(
    doc_id: int,
    chapter_index: int,
    *,
    prefetch_next: bool = True,
):
    job_id = _create_translate_job(
        doc_id,
        chapter_index=chapter_index,
        prefetch_next=prefetch_next,
    )
    if not job_id or not settings.inline_worker:
        return
    reading_processor.start_chapter_translation(
        doc_id,
        chapter_index,
        prefetch_next=prefetch_next,
        job_id=job_id,
    )


@router.get("", response_model=list[schemas.ReadingRead])
def list_readings(
    local: bool = False,
    session: Session = Depends(database.session_dependency),
):
    return crud.list_readings(session, local_only=local)


@router.get("/library/books", response_model=list[schemas.LibraryBookRead])
def list_library_books(session: Session = Depends(database.session_dependency)):
    books = book_library.list_books(session)
    return [_enrich_library_book(session, book) for book in books]


@router.post("/library/books/{book_key}/import")
async def import_library_book(book_key: str, session: Session = Depends(database.session_dependency)):
    try:
        book, doc, created = book_library.import_book(session, book_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="书库目录项不存在")
    except ValueError as e:
        book_library.mark_failed(session, book_key, str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        book_library.mark_failed(session, book_key, str(e))
        raise HTTPException(status_code=500, detail=f"导入书籍失败：{e}") from e

    if created:
        pass  # 懒翻译：打开章节后再译
    return {
        "ok": True,
        "created": created,
        "book": _enrich_library_book(session, book),
        "reading": schemas.ReadingRead.model_validate(doc),
    }


@router.post("/library/books/{book_key}/refresh")
def refresh_library_book(book_key: str, session: Session = Depends(database.session_dependency)):
    try:
        book = book_library.refresh_book_cache(session, book_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="书库目录项不存在")
    except Exception as e:
        book_library.mark_failed(session, book_key, str(e))
        raise HTTPException(status_code=500, detail=f"重新下载失败：{e}") from e
    return {"ok": True, "book": _enrich_library_book(session, book)}


@router.delete("/library/books/{book_key}/import")
def unlink_library_book(
    book_key: str,
    delete_reading: bool = Query(False),
    session: Session = Depends(database.session_dependency),
):
    try:
        book = book_library.unlink_book(session, book_key, delete_reading=delete_reading)
    except KeyError:
        raise HTTPException(status_code=404, detail="书库目录项不存在")
    return {"ok": True, "book": _enrich_library_book(session, book)}


@router.post("/library/books/{book_key}/reimport")
async def reimport_library_book(book_key: str, session: Session = Depends(database.session_dependency)):
    try:
        book, doc, created = book_library.reimport_book(session, book_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="书库目录项不存在")
    except ValueError as e:
        book_library.mark_failed(session, book_key, str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        book_library.mark_failed(session, book_key, str(e))
        raise HTTPException(status_code=500, detail=f"重新导入失败：{e}") from e
    return {
        "ok": True,
        "created": created,
        "book": _enrich_library_book(session, book),
        "reading": schemas.ReadingRead.model_validate(doc),
    }


@router.post("", response_model=schemas.ReadingRead)
async def create_reading(
    request: schemas.ReadingCreate,
    session: Session = Depends(database.session_dependency),
):
    content = (request.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(content) > MAX_CONTENT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"文本过长（{len(content):,} 字符，上限 {MAX_CONTENT_CHARS:,}）",
        )
    doc = crud.create_reading(
        session,
        request.title,
        content,
        source_type=request.source_type or "paste",
        source_url=request.source_url,
        source_filename=request.source_filename,
    )
    return doc


@router.post("/upload", response_model=schemas.ReadingRead)
async def upload_reading(
    file: UploadFile = File(...),
    title: str = Form(""),
    session: Session = Depends(database.session_dependency),
):
    name = file.filename or "document.txt"
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（{(len(raw) / 1024 / 1024):.1f}MB，上限 {MAX_UPLOAD_BYTES // 1024 // 1024}MB）",
        )
    try:
        title_hint, content, source_type = parse_upload(name, raw)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(content) > MAX_CONTENT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"文本过长（{len(content):,} 字符，上限 {MAX_CONTENT_CHARS:,}）",
        )

    doc_title = title.strip() or title_hint
    doc = crud.create_reading(
        session,
        doc_title,
        content,
        source_type=source_type,
        source_filename=name,
    )
    return doc


@router.get("/{doc_id}", response_model=schemas.ReadingRead)
def get_reading(doc_id: int, session: Session = Depends(database.session_dependency)):
    doc = reading_cache.get_doc(doc_id, session)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/{doc_id}/toc", response_model=schemas.ReadingToc)
def reading_toc(doc_id: int, session: Session = Depends(database.session_dependency)):
    doc = crud.get_reading(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    chapters = crud.list_reading_chapters(session, doc_id)
    return schemas.ReadingToc(
        chapters=[schemas.ReadingChapterRead.model_validate(item) for item in chapters],
        chapter_count=len(chapters),
        block_count=doc.block_count,
    )


@router.get("/{doc_id}/chapters/{chapter_index}/blocks", response_model=schemas.ReadingChapterBlocksPage)
def get_chapter_blocks(
    doc_id: int,
    chapter_index: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    chapter, items, total = crud.get_reading_chapter_blocks_page(
        session,
        doc_id,
        chapter_index,
        offset=offset,
        limit=limit,
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    return schemas.ReadingChapterBlocksPage(
        chapter=schemas.ReadingChapterRead.model_validate(chapter),
        items=items,
        offset=offset,
        limit=limit,
        total=total,
        has_more=offset + len(items) < total,
    )


@router.get("/{doc_id}/bootstrap", response_model=schemas.ReadingBootstrap)
async def reading_bootstrap(
    doc_id: int,
    limit: int = Query(100, ge=1, le=200),
    include_annotations: bool = Query(False),
    session: Session = Depends(database.session_dependency),
):
    """阅读器首屏聚合：元数据 + 当前章段落 + 目录；标注默认懒加载"""
    from app.services.reading_chapters import chapter_for_block

    doc = reading_cache.get_doc(doc_id, session)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    chapters = crud.list_reading_chapters(session, doc_id)
    chapter_idx = chapter_for_block(chapters, doc.last_block_index or 0)
    chapter = chapters[chapter_idx] if chapters else None
    if chapter:
        reading_cache.warm_doc(session, doc_id, first_pages=2)
        _, blocks, chapter_total = crud.get_reading_chapter_blocks_page(
            session,
            doc_id,
            chapter_idx,
            offset=0,
            limit=limit,
        )
    else:
        blocks, chapter_total = [], 0
    _start_chapter_translate(doc_id, chapter_idx, prefetch_next=True)
    highlights = crud.list_highlights(session, doc_id) if include_annotations else []
    notes_raw = crud.list_notes(session, doc_id) if include_annotations else []
    notes = (
        [schemas.NoteRead.model_validate(item) for item in crud.enrich_notes_with_block_index(session, notes_raw)]
        if include_annotations
        else []
    )
    return schemas.ReadingBootstrap(
        doc=doc,
        blocks=blocks,
        chapters=[schemas.ReadingChapterRead.model_validate(item) for item in chapters],
        chapter_index=chapter_idx,
        highlights=highlights,
        notes=notes,
        bookmarks=crud.list_bookmarks(session, doc_id) if include_annotations else [],
        vocab_stats=crud.get_reading_vocab_stats(session, doc_id),
        blocks_offset=0,
        blocks_limit=limit,
        blocks_total=doc.block_count,
        has_more_blocks=chapter is not None and len(blocks) < chapter_total,
        chapter_block_total=chapter_total if chapter else 0,
        has_more_chapters=chapter is not None and chapter_idx + 1 < len(chapters),
    )


@router.get("/{doc_id}/blocks", response_model=list[schemas.ReadingBlockRead] | schemas.ReadingBlocksPage)
def get_blocks(
    doc_id: int,
    offset: int | None = Query(None, ge=0),
    limit: int | None = Query(None, ge=1, le=200),
    session: Session = Depends(database.session_dependency),
):
    if not reading_cache.get_doc(doc_id, session):
        raise HTTPException(status_code=404, detail="文档不存在")
    if offset is None and limit is None:
        return reading_cache.get_all_blocks(session, doc_id)
    off = offset or 0
    lim = limit or 50
    total, items = reading_cache.get_blocks_page(session, doc_id, off, lim)
    return schemas.ReadingBlocksPage(
        items=items,
        offset=off,
        limit=lim,
        total=total,
        has_more=off + len(items) < total,
    )


@router.get("/{doc_id}/stream")
async def reading_stream(
    doc_id: int,
    request: Request,
    chapter_index: int | None = Query(None, ge=0),
):
    with Session(database.engine) as session:
        doc = crud.get_reading(session, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        scoped_user_id = doc.user_id
        if chapter_index is not None:
            _, blocks, _ = crud.get_reading_chapter_blocks_page(
                session, doc_id, chapter_index, offset=0, limit=10_000
            )
        else:
            _, blocks = reading_cache.get_blocks_page(session, doc_id, 0, 200)
        status_payload = {
            "translate_status": doc.translate_status,
            "translate_progress": doc.translate_progress,
            "translated_blocks": doc.translated_blocks,
            "block_count": doc.block_count,
            "status_message": doc.status_message or "",
            "chapter_index": chapter_index,
        }
        already_done = doc.translate_status == "done"
        pending = doc.translate_status == "translating" or reading_processor.is_translating(doc_id)
        cached_translations = [
            {"block_id": b.id, "order_index": b.order_index, "translation": b.translation}
            for b in blocks if b.translation
        ]

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _sse_subscribers[doc_id].add(queue)

    async def event_stream():
        try:
            yield f"event: status\ndata: {json.dumps(status_payload, ensure_ascii=False)}\n\n"
            for item in cached_translations:
                yield f"event: translated\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
            if already_done:
                yield f"event: done\ndata: {json.dumps({'translate_status': 'done'}, ensure_ascii=False)}\n\n"
            elif pending:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                        if event in ("done", "error"):
                            break
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
                        with Session(database.engine) as session:
                            cur = crud.get_reading(session, doc_id, user_id=scoped_user_id)
                            if cur and cur.translate_status in ("done", "failed"):
                                status = cur.translate_status
                                payload = {
                                    "translate_status": status,
                                    "status_message": cur.status_message or "",
                                }
                                if status == "failed":
                                    payload["message"] = cur.status_message or "翻译失败"
                                yield f"event: {status if status == 'done' else 'error'}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                break
        finally:
            _sse_subscribers[doc_id].discard(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{doc_id}/vocab-words", response_model=schemas.ReadingVocabStats)
def get_vocab_words(doc_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return crud.get_reading_vocab_stats(session, doc_id)


@router.patch("/{doc_id}/progress", response_model=schemas.ReadingRead)
def save_progress(
    doc_id: int,
    body: schemas.ReadingProgressUpdate,
    session: Session = Depends(database.session_dependency),
):
    doc = crud.update_reading_progress(session, doc_id, body.block_index)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/{doc_id}/search", response_model=list[schemas.ReadingSearchHit])
def search_reading(
    doc_id: int,
    q: str = Query(..., min_length=2),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return crud.search_reading_blocks(session, doc_id, q, limit=limit)


@router.get("/{doc_id}/bookmarks", response_model=list[schemas.BookmarkRead])
def list_bookmarks(doc_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return crud.list_bookmarks(session, doc_id)


@router.post("/{doc_id}/bookmarks", response_model=schemas.BookmarkRead)
def create_bookmark(
    doc_id: int,
    body: schemas.BookmarkCreate,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    try:
        return crud.create_bookmark(session, doc_id, body.block_index, body.label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/{doc_id}/bookmarks/{bookmark_id}", response_model=schemas.BookmarkRead)
def update_bookmark(
    doc_id: int,
    bookmark_id: int,
    body: schemas.BookmarkUpdate,
    session: Session = Depends(database.session_dependency),
):
    bm = crud.update_bookmark(session, doc_id, bookmark_id, body.label)
    if not bm:
        raise HTTPException(status_code=404, detail="书签不存在")
    return bm


@router.delete("/{doc_id}/bookmarks/{bookmark_id}")
def delete_bookmark(doc_id: int, bookmark_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.delete_bookmark(session, doc_id, bookmark_id):
        raise HTTPException(status_code=404, detail="书签不存在")
    return {"ok": True}


@router.get("/{doc_id}/highlights", response_model=list[schemas.HighlightRead])
def list_highlights(doc_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return crud.list_highlights(session, doc_id)


@router.post("/{doc_id}/highlights", response_model=schemas.HighlightRead)
def create_highlight(
    doc_id: int,
    body: schemas.HighlightCreate,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    block = crud.get_block(session, body.block_id)
    if not block or block.document_id != doc_id:
        raise HTTPException(status_code=400, detail="段落不存在")
    try:
        return crud.create_highlight(session, doc_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{doc_id}/highlights/{highlight_id}")
def delete_highlight(doc_id: int, highlight_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.delete_highlight(session, doc_id, highlight_id):
        raise HTTPException(status_code=404, detail="高亮不存在")
    return {"ok": True}


@router.get("/{doc_id}/notes", response_model=list[schemas.NoteRead])
def list_notes(doc_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    notes = crud.list_notes(session, doc_id)
    return [schemas.NoteRead.model_validate(item) for item in crud.enrich_notes_with_block_index(session, notes)]


@router.post("/{doc_id}/notes", response_model=schemas.NoteRead)
def create_note(
    doc_id: int,
    body: schemas.NoteCreate,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading(session, doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    if not (body.content or "").strip():
        raise HTTPException(status_code=400, detail="笔记内容不能为空")
    try:
        crud.validate_note_refs(session, doc_id, body.block_id, body.highlight_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return crud.create_note(session, doc_id, body.model_dump())


@router.patch("/{doc_id}/notes/{note_id}", response_model=schemas.NoteRead)
def update_note(
    doc_id: int,
    note_id: int,
    body: schemas.NoteUpdate,
    session: Session = Depends(database.session_dependency),
):
    note = crud.update_note(session, doc_id, note_id, body.content)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@router.delete("/{doc_id}/notes/{note_id}")
def delete_note(doc_id: int, note_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.delete_note(session, doc_id, note_id):
        raise HTTPException(status_code=404, detail="笔记不存在")
    return {"ok": True}


@router.patch("/{doc_id}", response_model=schemas.ReadingRead)
def update_reading(
    doc_id: int,
    body: schemas.ReadingUpdate,
    session: Session = Depends(database.session_dependency),
):
    doc = crud.update_reading_title(session, doc_id, body.title)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.post("/{doc_id}/migrate-vocab")
def migrate_vocab_to_reading(
    doc_id: int,
    body: schemas.VocabMigrateRequest,
    session: Session = Depends(database.session_dependency),
):
    doc = crud.get_reading(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    to_id = f"reading-{doc_id}"
    count = crud.migrate_vocab_source(
        session,
        body.from_source_id,
        to_id,
        source_platform=body.source_platform,
        source_url=body.source_url or f"/reader?id={doc_id}",
        source_title=body.source_title or doc.title,
    )
    return {"ok": True, "migrated": count}


@router.post("/{doc_id}/translate/chapter/{chapter_index}")
async def translate_chapter(
    doc_id: int,
    chapter_index: int,
    prefetch_next: bool = Query(True),
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_reading_chapter(session, doc_id, chapter_index):
        raise HTTPException(status_code=404, detail="章节不存在")
    _start_chapter_translate(doc_id, chapter_index, prefetch_next=prefetch_next)
    return {"ok": True, "chapter_index": chapter_index}


@router.post("/{doc_id}/translate")
async def retranslate(doc_id: int, session: Session = Depends(database.session_dependency)):
    doc, needs_work = crud.prepare_retranslate_missing(session, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    if needs_work:
        reading_cache.invalidate_doc(doc_id)
        job_id = _create_translate_job(doc_id, force=False)
        if job_id and settings.inline_worker:
            reading_processor.start_untranslated_translation(doc_id, job_id=job_id)
    return {
        "ok": True,
        "queued": needs_work,
        "translated_blocks": doc.translated_blocks,
        "block_count": doc.block_count,
    }


@router.delete("/{doc_id}")
def delete_reading(
    doc_id: int,
    delete_vocab: bool = False,
    session: Session = Depends(database.session_dependency),
):
    if not crud.delete_reading(session, doc_id, delete_vocab=delete_vocab):
        raise HTTPException(status_code=404, detail="文档不存在")
    reading_cache.invalidate_doc(doc_id)
    return {"ok": True}
