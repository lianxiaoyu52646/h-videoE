"""Mobile product smoke tests: bilingual import + PK rooms."""
from app.services.text_splitter import split_into_blocks


def test_bilingual_lines_split_into_translation():
    text = "Hello world|||你好，世界\n\nGood morning|||早上好"
    blocks = split_into_blocks(text)
    assert len(blocks) >= 2
    assert blocks[0]["text"] == "Hello world"
    assert blocks[0]["translation"] == "你好，世界"


def test_create_bilingual_reading(client):
    resp = client.post(
        "/api/readings",
        json={
            "title": "Bilingual Demo",
            "content": "Apple is red.|||苹果是红色的。\n\nI like cats.|||我喜欢猫。",
        },
    )
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc["translate_status"] == "done"
    blocks = client.get(f"/api/readings/{doc['id']}/blocks").json()
    items = blocks.get("items") if isinstance(blocks, dict) else blocks
    assert items[0]["translation"]


def test_pk_bot_room_create(client):
    resp = client.post("/api/pk/rooms", json={"mode": "bot"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "bot"
    assert data["code"]
    assert data["status"] == "waiting"
    assert len(data["players"]) >= 2


def test_mobile_app_route(client):
    # default desktop mode still serves classic home
    resp = client.get("/app")
    assert resp.status_code == 200
    assert b"WordPop" in resp.content or b"view-read" in resp.content
