import json
import re
import urllib.request

WORD_RE = re.compile(r"[^A-Za-z'-]")


def norm(w: str) -> str:
    return WORD_RE.sub("", (w or "").strip().lower())


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "VideoEnglish/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def count_json_sentence(prefix: str, files: list[str]) -> int:
    merged: set[str] = set()
    base = (
        "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/"
        "json_original/json-sentence"
    )
    for name in files:
        data = json.loads(fetch(f"{base}/{name}.json"))
        for item in data:
            word = norm(item.get("word", ""))
            if word:
                merged.add(word)
    print(f"{prefix} json-sentence ({len(files)} files): {len(merged)}")
    return len(merged)


def try_txt(path: str) -> int | None:
    url = f"https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/{path}"
    try:
        text = fetch(url).decode("utf-8", "ignore")
    except Exception:
        return None
    words: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        word = line.split("\t", 1)[0].strip() if "\t" in line else line.split()[0]
        w = norm(word)
        if w:
            words.add(w)
    print(f"txt {path}: {len(words)}")
    return len(words)


CET4_JSON = ["CET4_1", "CET4_2", "CET4_3", "CET4luan_1", "CET4luan_2"]
count_json_sentence("CET4", CET4_JSON)

for path in [
    "word/CET4_1.txt",
    "words/CET4_1.txt",
    "vocabulary/CET4_1.txt",
    "json_original/word/CET4_1.txt",
    "json_original/words/CET4_1.txt",
    "json_original/txt/CET4_1.txt",
    "json_original/txt/CET4luan_1.txt",
    "CET4luan_1.txt",
    "txt/CET4_1.txt",
    "txt/CET4luan_1.txt",
    "json_original/json/CET4_1.json",
]:
    try_txt(path)
