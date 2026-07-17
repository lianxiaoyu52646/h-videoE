from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from app import database, security
from app.config import settings
from app.services import book_library, wordbook_catalog


SUMMARY_PATH = Path(__file__).resolve().parents[1] / "app" / "assets" / "curated" / "preinstall_summary.json"


def main() -> None:
    settings.ensure_runtime_dirs()
    database.init_db()

    with Session(database.engine) as session:
        user = security.ensure_default_user(session)
        token = security.set_current_user(user.id)
        try:
            wordbook_rows = wordbook_catalog.ensure_catalog(session)
            installed_wordbooks: list[dict] = []
            for item in wordbook_rows:
                row, wb, count = wordbook_catalog.install_catalog_wordbook(session, item.key)
                installed_wordbooks.append(
                    {
                        "key": row.key,
                        "wordbook_id": wb.id,
                        "name": wb.name,
                        "entry_count": count,
                    }
                )

            book_rows = book_library.ensure_catalog(session)
            installed_books: list[dict] = []
            for item in book_rows:
                book, doc, created = book_library.import_book(session, item.key)
                installed_books.append(
                    {
                        "key": book.key,
                        "title": book.title,
                        "reading_document_id": doc.id,
                        "created": created,
                        "block_count": doc.block_count,
                        "cache_status": book.cache_status,
                        "cache_path": book.cache_path,
                    }
                )
        finally:
            security.reset_current_user(token)

    summary = {
        "wordbooks": installed_wordbooks,
        "books": installed_books,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
