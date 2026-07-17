"""有道词典/段落翻译联网测试"""
import pytest

from app.services import youdao_translator

pytestmark = pytest.mark.network


def test_youdao_lookup_wizard(client):
    r = client.get("/api/word/wizard")
    assert r.status_code == 200
    data = r.json()
    assert data["word"] == "wizard"
    assert data.get("youdao_translation") or data.get("translation")


def test_youdao_prefers_chinese(client):
    r = client.get("/api/word/magic")
    assert r.status_code == 200
    data = r.json()
    zh = data.get("translation") or ""
    assert any("\u4e00" <= c <= "\u9fff" for c in zh), f"期望中文释义，实际: {zh!r}"


def test_youdao_paragraph_translate():
    result = youdao_translator.translate_text(
        "The young wizard stood at the door, wondering what would happen next."
    )
    assert result
    assert any("\u4e00" <= c <= "\u9fff" for c in result), f"期望中文译文: {result!r}"
