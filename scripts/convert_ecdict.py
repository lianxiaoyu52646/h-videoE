"""
将 ECDICT CSV 全量导入 SQLite dictionary.db。

输出位置:
  - 项目根 directory.db
  - android/app/src/main/assets/dictionary.db  (Android)
  - app/assets/dictionaries/dictionary.db     (桌面端)

用法:
  python scripts/convert_ecdict.py [ecdict.csv路径]
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
import urllib.request
import zipfile

ECDICT_URL = "https://github.com/skywind3000/ECDICT/releases/download/1.0.4/ecdict.csv.zip"
DB_FILE = "dictionary.db"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIRS = [
    os.path.join(PROJECT_ROOT, "android", "app", "src", "main", "assets"),
    os.path.join(PROJECT_ROOT, "app", "assets", "dictionaries"),
]
DEFAULT_CSV_CANDIDATES = [
    os.path.join(PROJECT_ROOT, "ecdict.csv"),
    r"d:\lian\praPro\vocab_app\vocab_app\app\data\ecdict.csv",
]


def resolve_csv_path(arg: str | None) -> tuple[str, bool]:
    """返回 (csv路径, 是否为本次下载的临时文件，可安全删除)。"""
    if arg:
        if not os.path.isfile(arg):
            raise FileNotFoundError(f"CSV not found: {arg}")
        return os.path.abspath(arg), False

    for path in DEFAULT_CSV_CANDIDATES:
        if os.path.isfile(path):
            return os.path.abspath(path), False

    print("Local CSV not found, downloading ECDICT...")
    zip_path = os.path.join(PROJECT_ROOT, "ecdict.csv.zip")
    csv_path = os.path.join(PROJECT_ROOT, "ecdict.csv")
    with urllib.request.urlopen(ECDICT_URL, timeout=180) as response:
        with open(zip_path, "wb") as f:
            f.write(response.read())
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(PROJECT_ROOT)
    os.remove(zip_path)
    if not os.path.isfile(csv_path):
        raise FileNotFoundError("Download finished but ecdict.csv missing")
    return csv_path, True


def create_database(db_path: str):
    import sqlite3

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            phonetic TEXT,
            translation TEXT,
            exchange TEXT,
            tags TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX idx_word ON words(word)")
    conn.commit()
    return conn, cursor


def import_csv(conn, cursor, csv_path: str) -> int:
    print(f"Importing: {csv_path}")
    count = 0
    inserted = 0
    batch_size = 10000
    batch: list[tuple] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_word = (row.get("word") or "").strip()
            if not raw_word:
                continue

            word = raw_word.lower()
            phonetic = (row.get("phonetic") or "").strip()
            translation = (row.get("translation") or "").strip()
            # 若无中文释义，回退英文 definition
            if not translation:
                translation = (row.get("definition") or "").strip()
            exchange = (row.get("exchange") or "").strip()
            tags = (row.get("tag") or "").strip()

            batch.append((word, phonetic, translation, exchange, tags))
            count += 1

            if len(batch) >= batch_size:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO words (word, phonetic, translation, exchange, tags)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                conn.commit()
                inserted += len(batch)
                batch = []
                print(f"Processed {count} rows...")

    if batch:
        cursor.executemany(
            """
            INSERT OR IGNORE INTO words (word, phonetic, translation, exchange, tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            batch,
        )
        conn.commit()
        inserted += len(batch)

    real_count = cursor.execute("SELECT COUNT(*) FROM words").fetchone()[0]
    print(f"CSV rows with word: {count}")
    print(f"Unique words in DB: {real_count}")
    return real_count


def main():
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else None
    csv_path, is_temp = resolve_csv_path(csv_arg)

    work_db = os.path.join(PROJECT_ROOT, DB_FILE)
    conn, cursor = create_database(work_db)
    try:
        import_csv(conn, cursor, csv_path)
    finally:
        conn.close()

    db_size = os.path.getsize(work_db) / (1024 * 1024)
    print(f"Database saved to: {work_db}")
    print(f"Database size: {db_size:.2f} MB")

    for output_dir in OUTPUT_DIRS:
        os.makedirs(output_dir, exist_ok=True)
        target_path = os.path.join(output_dir, DB_FILE)
        shutil.copy2(work_db, target_path)
        print(f"Database copied to: {target_path}")

    if is_temp and os.path.exists(csv_path):
        os.remove(csv_path)
        print("Removed temporary downloaded CSV")


if __name__ == "__main__":
    main()
