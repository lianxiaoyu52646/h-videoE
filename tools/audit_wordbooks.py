from __future__ import annotations

import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "app" / "assets" / "curated"
CJK = re.compile(r"[\u4e00-\u9fff]")


def audit_entry(entry: dict) -> list[str]:
    issues: list[str] = []
    word = (entry.get("word") or "").strip()
    if not word:
        issues.append("missing_word")
    translation = (entry.get("translation") or "").strip()
    definition = (entry.get("definition") or "").strip()
    pronunciation = (entry.get("pronunciation") or "").strip()
    example = (entry.get("example") or "").strip()
    if not translation:
        issues.append("no_chinese")
    elif not CJK.search(translation):
        issues.append("translation_not_chinese")
    if translation and definition and translation == definition:
        issues.append("dup_translation_definition")
    if definition and CJK.search(definition) and translation:
        issues.append("chinese_in_definition")
    if not pronunciation:
        issues.append("no_phonetic")
    if not example:
        issues.append("no_example")
    return issues


KYLEBING_EXPECTED = {
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


def main() -> None:
    catalog = json.loads((BASE / "wordbook_catalog.json").read_text(encoding="utf-8"))
    catalog_keys = {item["key"] for item in catalog}
    files = {path.stem for path in (BASE / "wordbooks").glob("*.json")}

    print("=== CATALOG vs FILES ===")
    print("catalog:", len(catalog), "files:", len(files))
    print("in catalog not on disk:", sorted(catalog_keys - files))
    print("on disk not in catalog:", sorted(files - catalog_keys))

    print("\n=== PER-BOOK AUDIT ===")
    totals = {"books": 0, "entries": 0, "no_cn": 0, "no_ph": 0, "dup_tr_def": 0}
    for item in catalog:
        path = BASE / item["asset_file"]
        if not path.exists():
            print(item["key"], "MISSING FILE")
            continue
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries") or []
        actual = len(entries)
        declared = int(item.get("entry_count") or 0)
        words = [(e.get("word") or "").strip().lower() for e in entries if e.get("word")]
        dup_words = actual - len(set(words))
        no_cn = sum(1 for e in entries if not (e.get("translation") or "").strip())
        no_ph = sum(1 for e in entries if not (e.get("pronunciation") or "").strip())
        dup_tr_def = sum(
            1
            for e in entries
            if (e.get("translation") or "").strip()
            and (e.get("translation") or "").strip() == (e.get("definition") or "").strip()
        )
        sample_issues: dict[str, int] = {}
        for entry in entries[:200]:
            for issue in audit_entry(entry):
                sample_issues[issue] = sample_issues.get(issue, 0) + 1

        totals["books"] += 1
        totals["entries"] += actual
        totals["no_cn"] += no_cn
        totals["no_ph"] += no_ph
        totals["dup_tr_def"] += dup_tr_def

        expected = KYLEBING_EXPECTED.get(item["key"])
        print(
            f"{item['key']}: entries={actual} declared={declared} expected={expected} "
            f"count_ok={actual == declared} full_ok={actual == expected if expected else True} "
            f"dup_words={dup_words} no_cn={no_cn} no_ph={no_ph} dup_tr_def={dup_tr_def}"
        )
        if sample_issues:
            print("  sample_issues(first200):", sample_issues)
        if entries:
            e0 = entries[0]
            tr = (e0.get("translation") or "")[:40]
            ph = (e0.get("pronunciation") or "")[:50]
            print(f"  sample: {e0.get('word')} | {ph} | {tr}")

    print("\n=== TOTALS ===")
    print(totals)

    # legacy orphan files
    for key in sorted(files - catalog_keys):
        path = BASE / "wordbooks" / f"{key}.json"
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries") or []
        no_cn = sum(1 for e in entries if not (e.get("translation") or "").strip())
        print(f"legacy {key}: entries={len(entries)} no_cn={no_cn}")


if __name__ == "__main__":
    main()
