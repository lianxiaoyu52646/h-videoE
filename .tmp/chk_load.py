import sys
from pathlib import Path
root = Path(r"D:\lian\praPro\h-videoE")
sys.path.insert(0, str(root))
from app.database import engine, get_session
from app import crud
from sqlmodel import Session

with Session(engine) as session:
    items = crud.list_vocab_page(session, offset=0, limit=5)
    print("page", len(items))
    if items:
        c = items[0]
        print("word", c.word, "pron", c.pronunciation, "tr", c.translation)
    due = crud.get_due_vocab(session, __import__("datetime").datetime.utcnow(), limit=5)
    print("due", len(due))
print("runtime ok")
