"""Build gutenberg_100.json and download classic texts into app/assets/books/gutenberg/.

Respects Project Gutenberg access: polite delays, UTF-8 plain text URLs.
https://www.gutenberg.org/
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "app" / "assets" / "books" / "gutenberg"
CATALOG = ROOT / "app" / "assets" / "curated" / "gutenberg_100.json"

# Curated classics (Text# from Project Gutenberg)
CLASSICS: list[tuple[int, str, str, list[str]]] = [
    (1342, "Pride and Prejudice", "Jane Austen", ["romance", "classic"]),
    (158, "Emma", "Jane Austen", ["romance", "classic"]),
    (161, "Sense and Sensibility", "Jane Austen", ["romance", "classic"]),
    (141, "Mansfield Park", "Jane Austen", ["romance", "classic"]),
    (121, "Northanger Abbey", "Jane Austen", ["romance", "classic"]),
    (105, "Persuasion", "Jane Austen", ["romance", "classic"]),
    (11, "Alice's Adventures in Wonderland", "Lewis Carroll", ["fantasy", "children"]),
    (12, "Through the Looking-Glass", "Lewis Carroll", ["fantasy", "children"]),
    (84, "Frankenstein", "Mary Shelley", ["gothic", "sci-fi"]),
    (43, "The Strange Case of Dr. Jekyll and Mr. Hyde", "Robert Louis Stevenson", ["gothic"]),
    (16, "Peter Pan", "J. M. Barrie", ["fantasy", "children"]),
    (55, "The Wonderful Wizard of Oz", "L. Frank Baum", ["fantasy", "children"]),
    (35, "The Time Machine", "H. G. Wells", ["sci-fi"]),
    (36, "The War of the Worlds", "H. G. Wells", ["sci-fi"]),
    (159, "The Invisible Man", "H. G. Wells", ["sci-fi"]),
    (174, "The Picture of Dorian Gray", "Oscar Wilde", ["classic"]),
    (844, "The Importance of Being Earnest", "Oscar Wilde", ["drama"]),
    (1661, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", ["mystery"]),
    (244, "A Study in Scarlet", "Arthur Conan Doyle", ["mystery"]),
    (2852, "The Hound of the Baskervilles", "Arthur Conan Doyle", ["mystery"]),
    (863, "The Importance of Being Earnest (play)", "Oscar Wilde", ["drama"]),
    (345, "Dracula", "Bram Stoker", ["gothic", "horror"]),
    (1952, "The Yellow Wallpaper", "Charlotte Perkins Gilman", ["short"]),
    (1260, "Jane Eyre", "Charlotte Brontë", ["romance", "classic"]),
    (768, "Wuthering Heights", "Emily Brontë", ["romance", "gothic"]),
    (767, "Agnes Grey", "Anne Brontë", ["classic"]),
    (1400, "Great Expectations", "Charles Dickens", ["classic"]),
    (98, "A Tale of Two Cities", "Charles Dickens", ["classic"]),
    (730, "Oliver Twist", "Charles Dickens", ["classic"]),
    (580, "The Pickwick Papers", "Charles Dickens", ["classic"]),
    (46, "A Christmas Carol", "Charles Dickens", ["classic", "short"]),
    (766, "David Copperfield", "Charles Dickens", ["classic"]),
    (1023, "Bleak House", "Charles Dickens", ["classic"]),
    (963, "The Old Curiosity Shop", "Charles Dickens", ["classic"]),
    (2701, "Moby Dick; Or, The Whale", "Herman Melville", ["classic"]),
    (15, "Moby-Dick (alternate)", "Herman Melville", ["classic"]),
    (76, "Adventures of Huckleberry Finn", "Mark Twain", ["classic"]),
    (74, "The Adventures of Tom Sawyer", "Mark Twain", ["classic"]),
    (119, "A Connecticut Yankee in King Arthur's Court", "Mark Twain", ["classic"]),
    (1837, "The Prince and the Pauper", "Mark Twain", ["classic"]),
    (2591, "Grimms' Fairy Tales", "Jacob & Wilhelm Grimm", ["fairy-tale"]),
    (27200, "Fairy Tales of Hans Christian Andersen", "Hans Christian Andersen", ["fairy-tale"]),
    (5200, "Metamorphosis", "Franz Kafka", ["classic", "short"]),
    (2554, "Crime and Punishment", "Fyodor Dostoyevsky", ["classic"]),
    (28054, "The Brothers Karamazov", "Fyodor Dostoyevsky", ["classic"]),
    (1399, "Anna Karenina", "Leo Tolstoy", ["classic"]),
    (2600, "War and Peace", "Leo Tolstoy", ["classic"]),
    (6130, "The Iliad", "Homer", ["epic"]),
    (1727, "The Odyssey", "Homer", ["epic"]),
    (1497, "The Republic", "Plato", ["philosophy"]),
    (1232, "The Prince", "Niccolò Machiavelli", ["philosophy"]),
    (8800, "The Divine Comedy", "Dante Alighieri", ["epic"]),
    (996, "Don Quixote", "Miguel de Cervantes", ["classic"]),
    (1184, "The Count of Monte Cristo", "Alexandre Dumas", ["adventure"]),
    (1251, "Three Musketeers", "Alexandre Dumas", ["adventure"]),
    (139, "The Jungle Book", "Rudyard Kipling", ["children", "adventure"]),
    (236, "The Jungle Book (alt)", "Rudyard Kipling", ["children"]),
    (103, "Around the World in Eighty Days", "Jules Verne", ["adventure", "sci-fi"]),
    (164, "Twenty Thousand Leagues under the Sea", "Jules Verne", ["adventure", "sci-fi"]),
    (83, "From the Earth to the Moon", "Jules Verne", ["sci-fi"]),
    (120, "Treasure Island", "Robert Louis Stevenson", ["adventure"]),
    (4217, "Kidnapped", "Robert Louis Stevenson", ["adventure"]),
    (514, "Little Women", "Louisa May Alcott", ["classic"]),
    (2782, "Little Men", "Louisa May Alcott", ["classic"]),
    (37106, "Anne of Green Gables", "L. M. Montgomery", ["classic"]),
    (47, "Anne of Avonlea", "L. M. Montgomery", ["classic"]),
    (289, "The Secret Garden", "Frances Hodgson Burnett", ["children"]),
    (113, "The Secret Garden (alt)", "Frances Hodgson Burnett", ["children"]),
    (27761, "A Little Princess", "Frances Hodgson Burnett", ["children"]),
    (145, "Middlemarch", "George Eliot", ["classic"]),
    (550, "Silas Marner", "George Eliot", ["classic"]),
    (215, "The Call of the Wild", "Jack London", ["adventure"]),
    (910, "White Fang", "Jack London", ["adventure"]),
    (219, "Heart of Darkness", "Joseph Conrad", ["classic"]),
    (974, "The Secret Agent", "Joseph Conrad", ["classic"]),
    (2500, "Siddhartha", "Hermann Hesse", ["classic"]),
    (421, "Kidnapped (alt)", "Robert Louis Stevenson", ["adventure"]),
    (829, "Gulliver's Travels", "Jonathan Swift", ["classic"]),
    (3207, "Leviathan", "Thomas Hobbes", ["philosophy"]),
    (5827, "The Essays of Ralph Waldo Emerson", "Ralph Waldo Emerson", ["essay"]),
    (28, "Aesop's Fables", "Aesop", ["fable", "children"]),
    (32, "Herland", "Charlotte Perkins Gilman", ["classic"]),
    (41, "The Legend of Sleepy Hollow", "Washington Irving", ["short"]),
    (45, "Anne of the Island", "L. M. Montgomery", ["classic"]),
    (64, "The Scarlet Pimpernel", "Baroness Orczy", ["adventure"]),
    (205, "Walden", "Henry David Thoreau", ["essay"]),
    (25305, "The Interesting Narrative of the Life of Olaudah Equiano", "Olaudah Equiano", ["memoir"]),
    (100, "Complete Works of Shakespeare", "William Shakespeare", ["drama"]),
    (1513, "Romeo and Juliet", "William Shakespeare", ["drama"]),
    (1524, "Hamlet", "William Shakespeare", ["drama"]),
    (1533, "Macbeth", "William Shakespeare", ["drama"]),
    (2265, "King Lear", "William Shakespeare", ["drama"]),
    (1112, "The Tempest", "William Shakespeare", ["drama"]),
    (2267, "Othello", "William Shakespeare", ["drama"]),
    (2235, "A Midsummer Night's Dream", "William Shakespeare", ["drama"]),
    (2243, "Julius Caesar", "William Shakespeare", ["drama"]),
    (1522, "Much Ado About Nothing", "William Shakespeare", ["drama"]),
    (2264, "Twelfth Night", "William Shakespeare", ["drama"]),
    (1128, "Henry V", "William Shakespeare", ["drama"]),
    (1129, "As You Like It", "William Shakespeare", ["drama"]),
    (1103, "Richard III", "William Shakespeare", ["drama"]),
    (1041, "Shakespeare's Sonnets", "William Shakespeare", ["poetry"]),
    (123, "At the Mountains of Madness", "H. P. Lovecraft", ["horror"]),
    (50133, "The Great Gatsby", "F. Scott Fitzgerald", ["classic"]),
]

# Deduplicate by id, keep first 100
_seen: set[int] = set()
UNIQUE: list[tuple[int, str, str, list[str]]] = []
for item in CLASSICS:
    if item[0] in _seen:
        continue
    _seen.add(item[0])
    UNIQUE.append(item)
UNIQUE = UNIQUE[:100]


def build_catalog() -> list[dict]:
    rows = []
    for gid, title, author, tags in UNIQUE:
        rows.append(
            {
                "key": f"pg_{gid}",
                "provider": "gutenberg",
                "gutenberg_id": gid,
                "title": title,
                "author": author,
                "description": f"Project Gutenberg #{gid} — {title}",
                "language": "en",
                "repo_url": f"https://www.gutenberg.org/ebooks/{gid}",
                "raw_url": f"https://www.gutenberg.org/ebooks/{gid}.txt.utf-8",
                "asset_file": f"{gid}.txt",
                "tags": ["classic", "gutenberg", *tags],
            }
        )
    return rows


def download_one(item: dict, client: httpx.Client) -> tuple[str, bool, str]:
    gid = item["gutenberg_id"]
    dest = OUT_DIR / f"{gid}.txt"
    if dest.exists() and dest.stat().st_size > 2000:
        return item["key"], True, "exists"
    urls = [
        item["raw_url"],
        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}.txt",
        f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
    ]
    last_err = ""
    for url in urls:
        try:
            resp = client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}"
                continue
            text = resp.content.decode("utf-8", errors="replace")
            if len(text) < 500:
                last_err = "too short"
                continue
            dest.write_text(text, encoding="utf-8")
            return item["key"], True, url
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
    return item["key"], False, last_err


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = build_catalog()
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote catalog: {CATALOG} ({len(catalog)} books)")

    ok = 0
    fail = 0
    with httpx.Client(timeout=60, headers={"User-Agent": "WordPopReader/1.0 (educational)"}) as client:
        # Sequential + polite delay to respect Gutenberg robot policy
        for i, item in enumerate(catalog, 1):
            key, success, info = download_one(item, client)
            if success:
                ok += 1
                print(f"[{i}/{len(catalog)}] OK {key} ({info})")
            else:
                fail += 1
                print(f"[{i}/{len(catalog)}] FAIL {key}: {info}")
            time.sleep(1.2)
    print(f"Done. ok={ok} fail={fail} dir={OUT_DIR}")


if __name__ == "__main__":
    main()
