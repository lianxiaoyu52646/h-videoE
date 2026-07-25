import sqlite3
import os

db_path = 'C:/Users/74787/AppData/Local/VideoEnglish/data/videoenglish.sqlite3'
print(f'Database path: {db_path}')
print(f'File exists: {os.path.exists(db_path)}')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('\nTables in database:')
for t in tables:
    print(f'  {t[0]}')

print('\n=== Reading Documents ===')
try:
    cursor.execute('SELECT id, title, block_count FROM reading_documents')
    docs = cursor.fetchall()
    for doc in docs:
        print(f'ID: {doc[0]}, Title: {doc[1][:50]}, Blocks: {doc[2]}')
except Exception as e:
    print(f'Error reading reading_documents: {e}')

print('\n=== Chapters ===')
try:
    cursor.execute('SELECT reading_document_id, chapter_index, title, block_count FROM reading_chapters ORDER BY reading_document_id, chapter_index')
    chapters = cursor.fetchall()
    current_doc_id = None
    doc_chapter_count = 0
    for ch in chapters:
        if ch[0] != current_doc_id:
            if current_doc_id is not None:
                print(f'  -> Total chapters: {doc_chapter_count}')
            current_doc_id = ch[0]
            doc_chapter_count = 0
            print(f'\nDocument {ch[0]}:')
        print(f'  Ch{ch[1]}: {ch[2][:40]} ({ch[3]} blocks)')
        doc_chapter_count += 1
    if current_doc_id is not None:
        print(f'  -> Total chapters: {doc_chapter_count}')
except Exception as e:
    print(f'Error reading reading_chapters: {e}')

conn.close()
