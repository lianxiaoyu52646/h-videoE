"""从 EPUB 提取英文纯文本，按 spine 顺序保留章节"""
from __future__ import annotations

import io
import re
from html import unescape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    HAS_EPUB = True
except ImportError:
    HAS_EPUB = False

_SKIP_TITLE_RE = re.compile(
    r"^(cover|title\s*page|copyright|toc|table of contents|dedication|"
    r"acknowledgment|acknowledgement|about the author|also by|praise for|"
    r"contents|版权|封面|目录)$",
    re.I,
)


def _chapter_title_from_soup(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all(["h1", "h2", "h3", "title"]):
        t = tag.get_text(" ", strip=True)
        if t and len(t) < 120 and not _SKIP_TITLE_RE.match(t.strip()):
            return t
    return None


def _should_skip_chapter(title: str, text: str) -> bool:
    if _SKIP_TITLE_RE.match(title.strip()):
        return True
    if len(text) < 80:
        return True
    letters = len(re.findall(r"[A-Za-z]", text))
    return letters < 40


def _spine_document_items(book: epub.EpubBook) -> list:
    """按 spine 顺序取正文 HTML 项，跳过 nav"""
    id_to_item = {
        item.get_id(): item
        for item in book.get_items()
        if item.get_type() == ebooklib.ITEM_DOCUMENT
    }
    ordered = []
    seen = set()
    for idref, _linear in book.spine:
        item = id_to_item.get(idref)
        if item and idref not in seen:
            seen.add(idref)
            ordered.append(item)
    if not ordered:
        ordered = list(id_to_item.values())
    return ordered


def extract_text_from_epub(raw: bytes) -> tuple[str, str]:
    """返回 (title, plain_text)，章节间用 <<<SECTION:标题>>> 分隔"""
    if not HAS_EPUB:
        raise RuntimeError("未安装 ebooklib，请执行 pip install ebooklib")

    book = epub.read_epub(io.BytesIO(raw))
    title = (book.get_metadata("DC", "title") or [["Untitled"]])[0][0]
    parts: list[str] = []
    chapter_idx = 0

    for item in _spine_document_items(book):
        html = item.get_content().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        chapter_title = _chapter_title_from_soup(soup) or f"Chapter {chapter_idx + 1}"
        text = soup.get_text("\n")
        text = unescape(text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text or _should_skip_chapter(chapter_title, text):
            continue
        parts.append(f"<<<SECTION:{chapter_title}>>>\n{text}")
        chapter_idx += 1

    content = "\n\n".join(parts).strip()
    if not content:
        raise ValueError("EPUB 中未找到可读文本")
    return str(title or "Untitled"), content
