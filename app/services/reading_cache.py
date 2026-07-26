"""
阅读模块内存缓存 — 持久化在 SQLite，热数据在进程内存，打开书籍秒读。

缓存层级：
1. 文档元数据 doc:{id}
2. 段落分页 blocks:{id}:{offset}:{limit}
3. 小书全文 blocks:{id}:all（≤200 段）
"""
import threading
from collections import OrderedDict
from typing import Any, Optional

from sqlmodel import Session

from app import crud

_DEFAULT_PAGE = 50
_SMALL_BOOK_BLOCKS = 200
_MAX_CACHE_ENTRIES = 256


class _LRUCache:
    def __init__(self, maxsize: int = _MAX_CACHE_ENTRIES):
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
            self._data[key] = value
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def invalidate_doc(self, doc_id: int) -> None:
        prefix = f":{doc_id}:"
        with self._lock:
            for key in list(self._data):
                if f"doc:{doc_id}" == key or prefix in key or key == f"blocks:{doc_id}:all":
                    del self._data[key]

    def patch_block_translation(self, doc_id: int, order_index: int, translation: Optional[str]) -> None:
        with self._lock:
            for key, val in self._data.items():
                if not key.startswith(f"blocks:{doc_id}:"):
                    continue
                if not isinstance(val, list):
                    continue
                for block in val:
                    if getattr(block, "order_index", None) == order_index:
                        block.translation = translation


_cache = _LRUCache()


def _doc_key(doc_id: int) -> str:
    return f"doc:{doc_id}"


def _blocks_key(doc_id: int, offset: int, limit: int) -> str:
    return f"blocks:{doc_id}:{offset}:{limit}"


def _blocks_all_key(doc_id: int) -> str:
    return f"blocks:{doc_id}:all"


def clear_all() -> None:
    """测试/热重载时清空内存缓存"""
    with _cache._lock:
        _cache._data.clear()


def invalidate_doc(doc_id: int) -> None:
    _cache.invalidate_doc(doc_id)


def get_doc(doc_id: int, session: Session):
    key = _doc_key(doc_id)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    doc = crud.get_reading(session, doc_id)
    if doc:
        _cache.set(key, doc)
    return doc


def get_blocks_page(
    session: Session,
    doc_id: int,
    offset: int = 0,
    limit: int = _DEFAULT_PAGE,
):
    doc = get_doc(doc_id, session)
    if not doc:
        return None, []

    total = doc.block_count or 0
    if total <= _SMALL_BOOK_BLOCKS:
        all_key = _blocks_all_key(doc_id)
        all_blocks = _cache.get(all_key)
        if all_blocks is None:
            all_blocks = crud.get_reading_blocks(session, doc_id)
            _cache.set(all_key, all_blocks)
        page = all_blocks[offset : offset + limit]
        return total, page

    key = _blocks_key(doc_id, offset, limit)
    page = _cache.get(key)
    if page is None:
        try:
            from app.services.reading_materialize import ensure_reading_blocks_range

            ensure_reading_blocks_range(session, doc_id, offset, offset + limit - 1)
        except Exception:
            pass
        page = crud.get_reading_blocks_page(session, doc_id, offset, limit)
        _cache.set(key, page)
    return total, page


def get_all_blocks(session: Session, doc_id: int):
    doc = get_doc(doc_id, session)
    if not doc:
        return []
    total, blocks = get_blocks_page(session, doc_id, 0, max(doc.block_count, 1))
    if total <= _SMALL_BOOK_BLOCKS:
        return _cache.get(_blocks_all_key(doc_id)) or blocks
    return crud.get_reading_blocks(session, doc_id)


def warm_doc(session: Session, doc_id: int, first_pages: int = 2) -> None:
    """翻译完成或打开书籍时预热首屏段落"""
    doc = get_doc(doc_id, session)
    if not doc:
        return
    limit = _DEFAULT_PAGE
    for i in range(first_pages):
        offset = i * limit
        if offset >= (doc.block_count or 0):
            break
        get_blocks_page(session, doc_id, offset, limit)


def patch_block_translation(doc_id: int, order_index: int, translation: Optional[str]) -> None:
    """SSE/翻译写入后同步更新内存中的段落译文"""
    _cache.patch_block_translation(doc_id, order_index, translation)
