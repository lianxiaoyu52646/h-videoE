from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session

from app import crud, schemas
from app import database
from app.services import wordbook_catalog, wordbook_import
from app.services.wordbook_entry_format import normalize_catalog_entry

router = APIRouter(prefix="/api/wordbooks", tags=["wordbooks"])


def _catalog_to_read(row, manifest: dict | None = None) -> dict:
    data = schemas.WordBookCatalogRead.model_validate(row).model_dump()
    if manifest:
        data["category"] = manifest.get("category", "")
    return data


@router.get("", response_model=list[schemas.WordBookRead])
def list_wordbooks(
    custom: bool = False,
    session: Session = Depends(database.session_dependency),
):
    items = crud.list_wordbooks(session, custom_only=custom)
    return [crud.wordbook_to_read(session, item) for item in items]


@router.post("", response_model=schemas.WordBookRead)
def create_wordbook(body: schemas.WordBookCreate, session: Session = Depends(database.session_dependency)):
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="词书名称不能为空")
    item = crud.create_wordbook(
        session,
        body.name,
        description=body.description,
        language=body.language,
        source_name=body.source_name,
    )
    return crud.wordbook_to_read(session, item)


@router.get("/catalog", response_model=list[schemas.WordBookCatalogRead])
def list_catalog(session: Session = Depends(database.session_dependency)):
    rows = wordbook_catalog.list_catalog(session)
    manifest_map = {item["key"]: item for item in wordbook_catalog.load_manifest()}
    return [_catalog_to_read(row, manifest_map.get(row.key)) for row in rows]


@router.post("/catalog/{catalog_key}/install")
def install_catalog_wordbook(catalog_key: str, session: Session = Depends(database.session_dependency)):
    try:
        catalog_row, wordbook, imported_count = wordbook_catalog.install_catalog_wordbook(session, catalog_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="词书目录项不存在")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="词书快照文件缺失")
    return {
        "ok": True,
        "catalog": schemas.WordBookCatalogRead.model_validate(catalog_row),
        "wordbook": crud.wordbook_to_read(session, wordbook),
        "imported_count": imported_count,
    }


@router.delete("/{wordbook_id}")
def delete_wordbook(wordbook_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.soft_delete_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    return {"ok": True, "id": wordbook_id}


@router.get("/{wordbook_id}", response_model=schemas.WordBookRead)
def get_wordbook(wordbook_id: int, session: Session = Depends(database.session_dependency)):
    item = crud.get_wordbook(session, wordbook_id)
    if not item:
        raise HTTPException(status_code=404, detail="词书不存在")
    return crud.wordbook_to_read(session, item)


@router.get("/{wordbook_id}/entries", response_model=schemas.WordBookEntriesPage)
def list_entries(
    wordbook_id: int,
    page: int = 1,
    page_size: int = 10,
    q: str = "",
    only_saved: bool = False,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    safe_page_size = max(10, min(100, page_size))
    items, total = crud.list_wordbook_entries_page(
        session,
        wordbook_id,
        page=page,
        page_size=safe_page_size,
        query=q,
        only_saved=only_saved,
    )
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = min(max(1, page), total_pages)
    if safe_page != page:
        items, total = crud.list_wordbook_entries_page(
            session,
            wordbook_id,
            page=safe_page,
            page_size=safe_page_size,
            query=q,
            only_saved=only_saved,
        )
    return {
        "items": items,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "total_pages": total_pages,
        "query": q,
    }


@router.get("/{wordbook_id}/saved-words")
def list_saved_words(wordbook_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    words = crud.list_wordbook_saved_words(session, wordbook_id)
    return {"words": words, "count": len(words)}


@router.post("/{wordbook_id}/entries/import")
def import_entries(
    wordbook_id: int,
    body: schemas.WordBookImportRequest,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    count = crud.add_wordbook_entries(
        session,
        wordbook_id,
        [entry.model_dump() for entry in body.entries],
    )
    return {"ok": True, "count": count}


@router.post("/{wordbook_id}/entries/add", response_model=schemas.WordBookEntryRead)
def add_word_entry(
    wordbook_id: int,
    body: schemas.WordBookAddWordRequest,
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    word = (body.word or "").strip()
    if not word:
        raise HTTPException(status_code=400, detail="单词不能为空")
    try:
        entry = wordbook_import.add_word_to_wordbook(session, wordbook_id, word)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry


@router.post("/{wordbook_id}/entries/upload", response_model=schemas.WordBookImportResult)
async def upload_wordbook_entries(
    wordbook_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(database.session_dependency),
):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    filename = (file.filename or "").strip()
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"txt", "csv", "json", "xlsx", "xlsm"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="支持 txt / csv / json / xlsx 文件")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        result = wordbook_import.import_wordbook_file(session, wordbook_id, data, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/{wordbook_id}/learn")
def add_to_learning(wordbook_id: int, session: Session = Depends(database.session_dependency)):
    if not crud.get_wordbook(session, wordbook_id):
        raise HTTPException(status_code=404, detail="词书不存在")
    count = crud.add_wordbook_to_learning(session, wordbook_id)
    return {"ok": True, "count": count}
