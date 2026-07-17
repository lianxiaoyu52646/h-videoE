"""从 PDF 提取英文纯文本，按页保留章节标记"""
import io
import re

try:
    import fitz  # pymupdf

    HAS_PDF = True
except ImportError:
    HAS_PDF = False


def extract_text_from_pdf(raw: bytes) -> tuple[str, str]:
    if not HAS_PDF:
        raise RuntimeError("未安装 pymupdf，请执行 pip install pymupdf")

    doc = fitz.open(stream=raw, filetype="pdf")
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip() or "Untitled PDF"
    parts: list[str] = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            parts.append(f"<<<SECTION:Page {i + 1}>>>\n{text}")
    doc.close()

    content = re.sub(r"\n{3,}", "\n\n", "\n\n".join(parts)).strip()
    if not content:
        raise ValueError("PDF 中未找到可读文本（扫描版需 OCR）")
    return title, content
