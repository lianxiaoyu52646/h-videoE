"""将英文文本拆分为阅读段落，并识别章节标题"""

import re



SECTION_MARKER_RE = re.compile(r"^<<<SECTION:(.+?)>>>\s*$", re.MULTILINE)



_HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+)$"),
    re.compile(r"^(chapter|part|section|book|prologue|epilogue)\s+[\dIVXLCivxliv]+(?:[:\s\-—].*)?$", re.I),
    re.compile(r"^CHAPTER\s+\d+(?:[:\s\-—].*)?$", re.I),
    re.compile(r"^(chapter|part|section|book)\s+[A-Za-z][\w\s\-—:]*$", re.I),
    re.compile(r"^(story|tale|sketch|fairy tale|legend)\s+[\dIVXLCivxliv]+(?:[:\s\-—].*)?$", re.I),
    re.compile(r"^(book|part|volume)\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)(?:[:\s\-—].*)?$", re.I),
    re.compile(r"^[IVXLCDM]+\.?\s*$"),
    re.compile(r"^\*{3,}\s*$"),
]





def _is_heading(text: str) -> bool:

    line = text.strip()

    if not line or len(line) > 120:

        return False

    for pat in _HEADING_PATTERNS:

        if pat.match(line):

            return True

    alpha = re.sub(r"[^A-Za-z]", "", line)

    if alpha and line == line.upper() and len(line) < 80 and len(line.split()) <= 12:

        return True

    return False





def _clean_heading(text: str) -> str:

    line = text.strip()

    m = re.match(r"^#{1,6}\s+(.+)$", line)

    if m:

        return m.group(1).strip()

    return line





def _inject_gutenberg_section_markers(text: str) -> str:
    """Gutenberg 纯文本：独立成行的标题行注入 SECTION 标记，便于章节推导。"""
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        prev_blank = i == 0 or not lines[i - 1].strip()
        next_blank = i >= len(lines) - 1 or not lines[i + 1].strip()
        if prev_blank and next_blank and _is_heading(stripped):
            out.append(f"<<<SECTION:{_clean_heading(stripped)}>>>")
            continue
        out.append(line)
    return "\n".join(out)





def split_into_blocks(text: str, max_chars: int = 600) -> list[dict]:

    """返回 [{'text': str, 'section_title': str|None}, ...]"""

    text = text.replace("\r\n", "\n").strip()

    if not text:

        return []

    text = _inject_gutenberg_section_markers(text)



    sections: list[tuple[str | None, str]] = []

    if SECTION_MARKER_RE.search(text):

        last_end = 0

        current_title: str | None = None

        for match in SECTION_MARKER_RE.finditer(text):

            chunk = text[last_end : match.start()].strip()

            if chunk:

                sections.append((current_title, chunk))

            current_title = match.group(1).strip()

            last_end = match.end()

        tail = text[last_end:].strip()

        if tail:

            sections.append((current_title, tail))

    else:

        sections = [(None, text)]



    blocks: list[dict] = []

    for inherited_title, section_text in sections:

        blocks.extend(_split_section(section_text, inherited_title, max_chars))

    return blocks





def _split_section(text: str, inherited_title: str | None, max_chars: int) -> list[dict]:

    parts = re.split(r"\n\s*\n+", text)

    if len(parts) == 1 and "\n" in text:

        parts = [ln.strip() for ln in text.split("\n") if ln.strip()]



    blocks: list[dict] = []

    current_title = inherited_title



    for part in parts:

        part = part.strip()

        if not part:

            continue

        if _is_heading(part):

            current_title = _clean_heading(part)

            continue

        if len(part) <= max_chars:

            blocks.append({"text": part, "section_title": current_title})

            continue

        for chunk in _split_long_paragraph(part, max_chars):

            blocks.append({"text": chunk, "section_title": current_title})

    return blocks





def _split_long_paragraph(text: str, max_chars: int) -> list[str]:

    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: list[str] = []

    buf = ""

    for sent in sentences:

        sent = sent.strip()

        if not sent:

            continue

        if len(sent) > max_chars:

            if buf:

                chunks.append(buf.strip())

                buf = ""

            for i in range(0, len(sent), max_chars):

                chunks.append(sent[i : i + max_chars].strip())

            continue

        if buf and len(buf) + len(sent) + 1 > max_chars:

            chunks.append(buf.strip())

            buf = sent

        else:

            buf = f"{buf} {sent}".strip() if buf else sent

    if buf:

        chunks.append(buf.strip())

    return chunks


