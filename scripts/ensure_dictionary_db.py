"""Ensure app/assets/dictionaries/dictionary.db exists for ECDICT lookups.

Priority:
1. Already present dictionary.db → keep
2. ecdict.csv (repo root or ECDICT_CSV env) → convert via scripts/convert_ecdict.py
3. Skip quietly if neither exists (app still runs; lookups fall back to Youdao/cache)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "app" / "assets" / "dictionaries" / "dictionary.db"
CSV_CANDIDATES = [
    Path(os.getenv("ECDICT_CSV") or ""),
    ROOT / "ecdict.csv",
    ROOT / "app" / "assets" / "dictionaries" / "ecdict.csv",
]


def main() -> int:
    if DB.exists() and DB.stat().st_size > 1_000_000:
        print(f"dictionary.db ok: {DB} ({DB.stat().st_size} bytes)")
        return 0
    csv_path = next((p for p in CSV_CANDIDATES if p and p.is_file()), None)
    if not csv_path:
        print("No dictionary.db or ecdict.csv found; skip ECDICT build")
        return 0
    cmd = [sys.executable, str(ROOT / "scripts" / "convert_ecdict.py"), str(csv_path)]
    print("Building dictionary.db from", csv_path)
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
