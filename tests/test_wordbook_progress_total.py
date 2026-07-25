"""List card progress must use JSON catalog total, not sparse SQL entry count."""
from sqlmodel import Session

from app import crud, models, security
from app.services import wordbook_catalog, wordbook_study


def test_list_progress_uses_json_total_not_sparse_sql(client, test_engine, monkeypatch):
    monkeypatch.setattr("app.config.settings.auto_install_wordbooks", False)
    monkeypatch.setattr("app.config.settings.local_auto_user", True)
    monkeypatch.setattr("app.config.settings.app_mode", "desktop")

    with Session(test_engine) as session:
        user = security.ensure_default_user(session)
        token = security.set_current_user(user.id)
        try:
            _, wordbook, expected = wordbook_catalog.install_catalog_wordbook(
                session, "ielts_kylebing", user_id=user.id
            )
            assert expected > 100
            # Simulate starred sparse SQL rows (what made list show 3/3).
            for word in ("abandon", "ability", "able"):
                session.add(
                    models.WordBookEntry(
                        wordbook_id=wordbook.id,
                        word=word,
                        definition="",
                        translation="t",
                    )
                )
            session.commit()
            mem = wordbook_study.get_or_create_memory(session, wordbook.id, user_id=user.id)
            mem.cursor_offset = 53
            mem.total_count = 3  # stale / wrong
            mem.is_completed = True
            session.add(mem)
            session.commit()

            read = crud.wordbook_to_read(session, wordbook)
            assert read["entry_count"] == expected
            assert read["study_label"] == f"54 / {expected}"
            assert read["study_percent"] < 5
            assert "3 / 3" not in read["study_label"]
            # SQL sparse count must not become entry_count
            assert read["entry_count"] != 3
        finally:
            security.reset_current_user(token)
