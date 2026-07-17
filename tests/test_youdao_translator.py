"""有道翻译单元测试（mock，不联网）"""
from unittest.mock import patch

from app.services import youdao_translator


def test_translate_text_empty():
    assert youdao_translator.translate_text("") == ""
    assert youdao_translator.translate_text("   ") == ""


def test_translate_text_success():
    with patch.object(youdao_translator, "_request_jsonapi", return_value="你好世界"):
        assert youdao_translator.translate_text("Hello world") == "你好世界"


def test_translate_long_splits_and_joins():
    long_en = "A" * 900
    with patch.object(youdao_translator, "_request_jsonapi", side_effect=["前半", "后半"]):
        result = youdao_translator.translate_text(long_en, source="en")
    assert result == "前半 后半"


def test_extract_ec_translation_from_dict_payload():
    payload = {
        "ec": {
            "word": [
                {
                    "trs": [
                        {
                            "tr": [
                                {"l": {"i": ["结束；结局，剧终"]}},
                            ]
                        }
                    ]
                }
            ]
        }
    }
    assert youdao_translator._extract_ec_translation(payload) == "结束；结局，剧终"


def test_parse_jsonapi_response_prefers_fanyi():
    payload = {"fanyi": {"tran": "你好"}}
    assert youdao_translator._parse_jsonapi_response(payload) == "你好"


def test_parse_jsonapi_response_falls_back_to_ec():
    payload = {
        "ec": {
            "word": [{"trs": [{"tr": [{"l": {"i": ["是的。"]}}]}]}],
        }
    }
    assert youdao_translator._parse_jsonapi_response(payload) == "是的。"


def test_lookup_word_from_suggest():
    fake = {
        "data": {
            "entries": [
                {"entry": "wizard", "explain": "n. 巫师"},
            ]
        }
    }
    with patch("httpx.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = fake
        youdao_translator.lookup_word.cache_clear()
        assert youdao_translator.lookup_word("wizard") == "n. 巫师"
