from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.wordbook_entry_format import normalize_catalog_entry


BASE_DIR = ROOT / "app" / "assets" / "curated"
WORDBOOK_DIR = BASE_DIR / "wordbooks"
RAW_BASE = "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master"
KYLEBING_REPO = "https://github.com/KyleBing/english-vocabulary"

WORD_RE = re.compile(r"[^A-Za-z'-]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
BAD_TRANSLATION_RE = re.compile(r"中文释义[；;]?")

# KyleBing 全量去重后的 unique 词数（json-simple / 合并 txt 一致）
KYLEBING_EXPECTED: dict[str, int] = {
    "cet4_kylebing": 4544,
    "cet6_kylebing": 3992,
    "kaoyan_kylebing": 5047,
    "tem4_kylebing": 4340,
    "tem8_kylebing": 12410,
    "ielts_kylebing": 5275,
    "toefl_kylebing": 10367,
    "gre_kylebing": 9984,
    "gmat_kylebing": 3312,
    "sat_kylebing": 4464,
    "gaozhong_kylebing": 3743,
    "chuzhong_kylebing": 1987,
    "bec_kylebing": 2823,
}


def _source(
    key: str,
    *,
    name: str,
    level: str,
    category: str,
    json_files: list[str],
    txt_file: str | None = None,
) -> dict:
    return {
        "key": key,
        "name": name,
        "description": (
            f"KyleBing/english-vocabulary 全量词书（去重）· {level} · "
            "含中文释义；有例句的词条补全英美音标与例句。"
        ),
        "source_name": f"GitHub:{level}",
        "repo_url": KYLEBING_REPO,
        "level": level,
        "category": category,
        "json_files": json_files,
        "txt_file": txt_file,
    }


WORD_SOURCES: dict[str, dict] = {
    "cet4_kylebing": _source(
        "cet4_kylebing",
        name="大学英语四级词书",
        level="CET4",
        category="大学考试",
        txt_file="3 四级-乱序.txt",
        json_files=["CET4_1", "CET4_2", "CET4_3", "CET4luan_1", "CET4luan_2"],
    ),
    "cet6_kylebing": _source(
        "cet6_kylebing",
        name="大学英语六级词书",
        level="CET6",
        category="大学考试",
        txt_file="4 六级-乱序.txt",
        json_files=["CET6_1", "CET6_2", "CET6_3", "CET6luan_1"],
    ),
    "kaoyan_kylebing": _source(
        "kaoyan_kylebing",
        name="考研英语词书",
        level="KaoYan",
        category="大学考试",
        txt_file="5 考研-乱序.txt",
        json_files=["KaoYan_1", "KaoYan_2", "KaoYan_3", "KaoYanluan_1"],
    ),
    "tem4_kylebing": _source(
        "tem4_kylebing",
        name="英语专业四级词书",
        level="TEM4",
        category="大学考试",
        json_files=["Level4_1", "Level4_2", "Level4luan_1", "Level4luan_2"],
    ),
    "tem8_kylebing": _source(
        "tem8_kylebing",
        name="英语专业八级词书",
        level="TEM8",
        category="大学考试",
        json_files=["Level8_1", "Level8_2", "Level8luan_2"],
    ),
    "ielts_kylebing": _source(
        "ielts_kylebing",
        name="雅思 IELTS 词书",
        level="IELTS",
        category="出国留学",
        json_files=["IELTS_2", "IELTS_3", "IELTSluan_2"],
    ),
    "toefl_kylebing": _source(
        "toefl_kylebing",
        name="托福 TOEFL 词书",
        level="TOEFL",
        category="出国留学",
        txt_file="6 托福-乱序.txt",
        json_files=["TOEFL_2", "TOEFL_3"],
    ),
    "gre_kylebing": _source(
        "gre_kylebing",
        name="GRE 词书",
        level="GRE",
        category="出国留学",
        json_files=["GRE_2", "GRE_3"],
    ),
    "gmat_kylebing": _source(
        "gmat_kylebing",
        name="GMAT 词书",
        level="GMAT",
        category="出国留学",
        json_files=["GMAT_2", "GMAT_3", "GMATluan_2"],
    ),
    "sat_kylebing": _source(
        "sat_kylebing",
        name="SAT 词书",
        level="SAT",
        category="出国留学",
        txt_file="7 SAT-乱序.txt",
        json_files=["SAT_2", "SAT_3"],
    ),
    "gaozhong_kylebing": _source(
        "gaozhong_kylebing",
        name="高中英语词书",
        level="GaoZhong",
        category="中小学",
        txt_file="2 高中-乱序.txt",
        json_files=["GaoZhong_2", "GaoZhong_3", "GaoZhongluan_2"],
    ),
    "chuzhong_kylebing": _source(
        "chuzhong_kylebing",
        name="初中英语词书",
        level="ChuZhong",
        category="中小学",
        txt_file="1 初中-乱序.txt",
        json_files=["ChuZhong_2", "ChuZhong_3", "ChuZhongluan_2"],
    ),
    "bec_kylebing": _source(
        "bec_kylebing",
        name="BEC 商务英语词书",
        level="BEC",
        category="商务英语",
        json_files=["BEC_2", "BEC_3"],
    ),
}


def normalize_word(text: str) -> str:
    return WORD_RE.sub("", (text or "").strip().lower())


def clean_translation(text: str | None) -> str | None:
    value = BAD_TRANSLATION_RE.sub("", (text or "").strip())
    value = re.sub(r"[；;]{2,}", "；", value)
    value = value.strip("；; ")
    return value or None


def fetch_bytes(path: str, retries: int = 3) -> bytes:
    url = f"{RAW_BASE}/{urllib.parse.quote(path)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VideoEnglish/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.read()
        except Exception as exc:
            last_error = exc
            print(f"  retry fetch ({attempt + 1}/{retries}): {path}")
    raise RuntimeError(f"fetch failed: {path}") from last_error


def fetch_text(path: str) -> str:
    return fetch_bytes(path).decode("utf-8", "ignore")


def format_pronunciation(*, us: str | None = None, uk: str | None = None) -> str | None:
    def wrap(value: str) -> str:
        text = value.strip()
        if not text:
            return text
        if text.startswith("/") or text.startswith("["):
            return text
        return f"/{text}/"

    parts: list[str] = []
    if us:
        parts.append(f"美 {wrap(us)}")
    if uk and uk.strip() and uk.strip() != (us or "").strip():
        parts.append(f"英 {wrap(uk)}")
    elif uk and not us:
        parts.append(wrap(uk))
    return "  ".join(parts) if parts else None


def translations_from_simple_item(item: dict) -> tuple[str | None, str | None]:
    meaning_parts: list[str] = []
    part_of_speech = None
    for tr in item.get("translations") or []:
        translation = clean_translation((tr.get("translation") or "").strip())
        pos = (tr.get("type") or "").strip()
        if translation:
            meaning_parts.append(f"{pos}. {translation}" if pos else translation)
        if not part_of_speech and pos:
            part_of_speech = pos
    chinese = clean_translation("；".join(meaning_parts))
    return chinese, part_of_speech


def parse_json_simple(text: str, level: str) -> dict[str, dict]:
    items = json.loads(text)
    if not isinstance(items, list):
        items = [items]
    merged: dict[str, dict] = {}
    for item in items:
        word = normalize_word(item.get("word", ""))
        if not word:
            continue
        chinese, part_of_speech = translations_from_simple_item(item)
        entry = normalize_catalog_entry(
            {
                "word": word,
                "lemma": word,
                "translation": chinese,
                "definition": "",
                "pronunciation": None,
                "part_of_speech": part_of_speech,
                "example": None,
                "tags": [level.lower()],
                "level": level,
            }
        )
        if word in merged and entry.get("translation"):
            prev = (merged[word].get("translation") or "").strip()
            cur = (entry.get("translation") or "").strip()
            if cur and cur not in prev:
                entry["translation"] = clean_translation(f"{prev}；{cur}")
        merged[word] = entry
    return merged


def parse_json_sentence(text: str) -> dict[str, dict]:
    items = json.loads(text)
    merged: dict[str, dict] = {}
    for item in items:
        word = normalize_word(item.get("word", ""))
        if not word:
            continue
        chinese, part_of_speech = translations_from_simple_item(item)
        sentences = item.get("sentences") or []
        example = (sentences[0].get("sentence") or "").strip() if sentences else None
        merged[word] = {
            "translation": chinese,
            "part_of_speech": part_of_speech,
            "pronunciation": format_pronunciation(us=item.get("us"), uk=item.get("uk")),
            "example": example or None,
        }
    return merged


def parse_txt(text: str, level: str) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        word_raw, _, trans = raw.partition("\t")
        word = normalize_word(word_raw)
        if not word:
            continue
        translation = clean_translation(trans.strip())
        if word in merged:
            prev = (merged[word].get("translation") or "").strip()
            if translation and translation not in prev:
                translation = clean_translation(f"{prev}；{translation}")
        merged[word] = normalize_catalog_entry(
            {
                "word": word,
                "lemma": word,
                "translation": translation,
                "definition": "",
                "pronunciation": None,
                "part_of_speech": None,
                "example": None,
                "tags": [level.lower()],
                "level": level,
            }
        )
    return merged


def load_json_simple_files(files: list[str], level: str) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for name in files:
        path = f"json_original/json-simple/{name}.json"
        print(f"  simple {name}.json ...")
        chunk = parse_json_simple(fetch_text(path), level)
        for word, entry in chunk.items():
            if word in merged and entry.get("translation"):
                prev = (merged[word].get("translation") or "").strip()
                cur = (entry.get("translation") or "").strip()
                if cur and cur not in prev:
                    entry["translation"] = clean_translation(f"{prev}；{cur}")
            merged[word] = entry
    return merged


def load_json_sentence_files(files: list[str]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for name in files:
        path = f"json_original/json-sentence/{name}.json"
        print(f"  sentence {name}.json ...")
        for word, enrich in parse_json_sentence(fetch_text(path)).items():
            if word in merged:
                for key in ("translation", "part_of_speech", "pronunciation", "example"):
                    if not merged[word].get(key) and enrich.get(key):
                        merged[word][key] = enrich[key]
            else:
                merged[word] = enrich
    return merged


def merge_wordbook(meta: dict) -> list[dict]:
    level = meta["level"]
    base = load_json_simple_files(meta["json_files"], level)
    enrich = load_json_sentence_files(meta["json_files"])

    if meta.get("txt_file"):
        print(f"  txt {meta['txt_file']} ...")
        txt_map = parse_txt(fetch_text(meta["txt_file"]), level)
        missing = set(txt_map) - set(base)
        if missing:
            print(f"  warn: {len(missing)} txt words missing from json-simple, merging in")
            for word in missing:
                base[word] = txt_map[word]

    for word, entry in base.items():
        extra = enrich.get(word) or {}
        if extra.get("translation") and not entry.get("translation"):
            entry["translation"] = extra["translation"]
        if extra.get("part_of_speech") and not entry.get("part_of_speech"):
            entry["part_of_speech"] = extra["part_of_speech"]
        if extra.get("pronunciation"):
            entry["pronunciation"] = extra["pronunciation"]
        if extra.get("example"):
            entry["example"] = extra["example"]
        base[word] = normalize_catalog_entry(entry)

    return sorted(base.values(), key=lambda item: item["word"])


def sync_wordbooks(keys: list[str] | None = None) -> None:
    WORDBOOK_DIR.mkdir(parents=True, exist_ok=True)
    selected = keys or list(WORD_SOURCES.keys())
    catalog: list[dict] = []

    for key in selected:
        meta = WORD_SOURCES[key]
        print(f"sync {key} ...")
        entries = merge_wordbook(meta)
        expected = KYLEBING_EXPECTED.get(key)
        if expected and len(entries) < expected:
            print(f"  WARN count {len(entries)} < expected {expected}")
        elif expected:
            print(f"  ok count {len(entries)} (expected {expected})")

        asset_name = f"{key}.json"
        (WORDBOOK_DIR / asset_name).write_text(
            json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        catalog.append(
            {
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "source_name": meta["source_name"],
                "provider": "github",
                "repo_url": meta["repo_url"],
                "raw_url": f"{RAW_BASE}/json_original/json-simple/{meta['json_files'][0]}.json",
                "asset_file": f"wordbooks/{asset_name}",
                "entry_count": len(entries),
                "category": meta["category"],
                "expected_count": expected,
            }
        )

    if keys is None:
        (BASE_DIR / "wordbook_catalog.json").write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        catalog_path = BASE_DIR / "wordbook_catalog.json"
        existing = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else []
        merged = {item["key"]: item for item in existing}
        for item in catalog:
            merged[item["key"]] = item
        ordered = [merged[key] for key in WORD_SOURCES if key in merged]
        catalog_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")

    print("synced:", [(item["key"], item["entry_count"]) for item in catalog])


if __name__ == "__main__":
    sync_wordbooks(sys.argv[1:] if len(sys.argv) > 1 else None)
