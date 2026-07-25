"""One-shot: persist all 13 bundled wordbooks into the local SQLite DB."""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlmodel import Session, select, func

from app import database, models, security
from app.services import wordbook_catalog


def main() -> None:
    database.init_db()
    with Session(database.engine) as session:
        user = security.ensure_default_user(session)
        print("user:", user.id, user.email)
        result = wordbook_catalog.ensure_all_catalog_installed(session, user_id=user.id)
        print("result:", result)

        rows = session.exec(
            select(models.WordBookCatalog)
            .where(models.WordBookCatalog.user_id == user.id)
            .order_by(models.WordBookCatalog.key)
        ).all()
        total = 0
        for row in rows:
            n = 0
            if row.installed_wordbook_id:
                n = session.exec(
                    select(func.count(models.WordBookEntry.id)).where(
                        models.WordBookEntry.wordbook_id == row.installed_wordbook_id
                    )
                ).one()
            total += int(n or 0)
            print(f"  {row.key}: installed_id={row.installed_wordbook_id} entries={n}")
        print("TOTAL entries in catalog books:", total)


if __name__ == "__main__":
    main()
