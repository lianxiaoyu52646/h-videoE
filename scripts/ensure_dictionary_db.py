"""Ensure app/assets/dictionaries/dictionary.db exists for ECDICT lookups.

Priority:
1. Existing dictionary.db → keep
2. Local ecdict.csv → convert
3. Otherwise download ECDICT release zip and convert (for Render build)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "app" / "assets" / "dictionaries" / "dictionary.db"
CONVERT = ROOT / "scripts" / "convert_ecdict.py"
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
    if csv_path:
        cmd = [sys.executable, str(CONVERT), str(csv_path)]
        print("Building dictionary.db from", csv_path)
        return subprocess.call(cmd)

    # No local CSV — convert_ecdict.py downloads ECDICT 1.0.4 zip automatically
    print("No local ECDICT; downloading + building dictionary.db …")
    return subprocess.call([sys.executable, str(CONVERT)])


if __name__ == "__main__":
    raise SystemExit(main())
