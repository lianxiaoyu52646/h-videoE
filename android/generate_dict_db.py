import json
import sqlite3
import os

json_path = r'd:\lian\praPro\h-videoE\mobile\www\assets\core_en.json'
db_path = r'd:\lian\praPro\h-videoE\android\app\src\main\assets\dictionary.db'

os.makedirs(os.path.dirname(db_path), exist_ok=True)

if os.path.exists(db_path):
    os.remove(db_path)

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

entries = data.get('entries', [])
print(f'Loaded {len(entries)} words from JSON')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    phonetic TEXT DEFAULT '',
    translation TEXT DEFAULT '',
    exchange TEXT DEFAULT '',
    tags TEXT DEFAULT ''
)
''')

cursor.execute('CREATE INDEX idx_word ON words(word)')

for entry in entries:
    word = entry.get('word', '').lower()
    phonetic = entry.get('pronunciation', '')
    translation = entry.get('translation', '')
    cursor.execute(
        'INSERT INTO words (word, phonetic, translation, exchange, tags) VALUES (?, ?, ?, ?, ?)',
        (word, phonetic, translation, '', '')
    )

conn.commit()

cursor.execute('SELECT COUNT(*) FROM words')
count = cursor.fetchone()[0]
print(f'Inserted {count} words into database')

cursor.execute('SELECT word, phonetic, translation FROM words LIMIT 5')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} - {row[2][:30]}')

conn.close()
print(f'Database saved to {db_path}')
print(f'Database size: {os.path.getsize(db_path)} bytes')
