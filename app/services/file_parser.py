"""解析上传文件为英文纯文本"""
from app.services.epub_extractor import extract_text_from_epub
from app.services.pdf_extractor import extract_text_from_pdf


def parse_upload(filename: str, raw: bytes) -> tuple[str, str, str]:
    """返回 (title_hint, content, source_type)"""
    name = filename or "document.txt"
    lower = name.lower()

    if lower.endswith(".epub"):
        title, content = extract_text_from_epub(raw)
        return title, content, "epub"
    if lower.endswith(".pdf"):
        title, content = extract_text_from_pdf(raw)
        return title, content, "pdf"

    source_type = "upload"
    if lower.endswith((".txt", ".text")):
        source_type = "txt"
    elif lower.endswith(".md"):
        source_type = "markdown"

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    title_hint = name.rsplit(".", 1)[0]
    return title_hint, content.strip(), source_type
