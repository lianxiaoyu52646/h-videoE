import sqlite3
import json
import os

JSON_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mobile", "www", "assets", "core_en.json")
DB_FILE = "dictionary.db"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "android", "app", "src", "main", "assets")

def create_database():
    print("Creating SQLite database...")
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            phonetic TEXT,
            translation TEXT,
            exchange TEXT,
            tags TEXT
        )
    ''')

    cursor.execute('CREATE INDEX idx_word ON words(word)')

    cursor.execute('''
        CREATE VIRTUAL TABLE words_fts USING fts5(
            word,
            translation,
            content=words,
            content_rowid=id
        )
    ''')

    return conn, cursor

def import_json(conn, cursor):
    print("Importing JSON data...")
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for entry in data.get('entries', []):
        word = entry.get('word', '').strip()
        phonetic = entry.get('pronunciation', '').strip()
        translation = entry.get('translation', '').strip()
        exchange = ''
        tags = ''

        if word:
            cursor.execute('''
                INSERT OR IGNORE INTO words (word, phonetic, translation, exchange, tags)
                VALUES (?, ?, ?, ?, ?)
            ''', (word.lower(), phonetic, translation, exchange, tags))
            count += 1

    conn.commit()
    print(f"Building FTS index...")
    cursor.execute('INSERT INTO words_fts(words_fts) VALUES("rebuild")')
    conn.commit()

    print(f"Total imported: {count} words")
    return count

def main():
    if not os.path.exists(JSON_FILE):
        print(f"Error: {JSON_FILE} not found")
        return

    conn, cursor = create_database()
    try:
        import_json(conn, cursor)
    finally:
        conn.close()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    target_path = os.path.join(OUTPUT_DIR, DB_FILE)
    if os.path.exists(target_path):
        os.remove(target_path)
    os.rename(DB_FILE, target_path)
    print(f"Database saved to: {target_path}")

    db_size = os.path.getsize(target_path) / (1024 * 1024)
    print(f"Database size: {db_size:.2f} MB")
    print("\n=== IMPORTANT ===")
    print("This script only imports core_en.json (~900 words).")
    print("For full ECDICT (~770,000 words):")
    print("  python scripts/convert_ecdict.py [path/to/ecdict.csv]")

if __name__ == "__main__":
    main()