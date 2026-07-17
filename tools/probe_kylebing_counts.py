import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".tmp" / "kylebing-vocab"
WORD_RE = re.compile(r"[^A-Za-z'-]")


def norm(w: str) -> str:
    return WORD_RE.sub("", (w or "").strip().lower())


def count_txt(path: Path) -> int:
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        w = norm(line.split("\t", 1)[0])
        if w:
            words.add(w)
    return len(words)


def count_json_simple(glob: str) -> int:
    words: set[str] = set()
    for path in ROOT.glob(f"json_original/json-simple/{glob}"):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for item in items:
            w = norm(item.get("word", ""))
            if w:
                words.add(w)
    return len(words)


def count_json_sentence(glob: str) -> int:
    words: set[str] = set()
    for path in ROOT.glob(f"json_original/json-sentence/{glob}"):
        for item in json.loads(path.read_text(encoding="utf-8")):
            w = norm(item.get("word", ""))
            if w:
                words.add(w)
    return len(words)


pairs = [
    ("cet4", "3 四级-乱序.txt", "CET4*.json"),
    ("cet6", "4 六级-乱序.txt", "CET6*.json"),
    ("kaoyan", "5 考研-乱序.txt", "KaoYan*.json"),
    ("toefl", "6 托福-乱序.txt", "TOEFL*.json"),
    ("sat", "7 SAT-乱序.txt", "SAT*.json"),
    ("chuzhong", "1 初中-乱序.txt", "ChuZhong*.json"),
    ("gaozhong", "2 高中-乱序.txt", "GaoZhong*.json"),
    ("ielts", None, "IELTS*.json"),
    ("gre", None, "GRE*.json"),
    ("gmat", None, "GMAT*.json"),
    ("bec", None, "BEC*.json"),
    ("tem4", None, "Level4*.json"),
    ("tem8", None, "Level8*.json"),
]

for name, txt, glob in pairs:
    txt_count = count_txt(ROOT / txt) if txt else None
    simple = count_json_simple(glob)
    sentence = count_json_sentence(glob)
    txt_lines = 0
    if txt:
        txt_lines = len([l for l in (ROOT / txt).read_text(encoding="utf-8").splitlines() if l.strip()])
    print(f"{name:8} txt_lines={txt_lines} txt_unique={txt_count} simple={simple} sentence={sentence}")
