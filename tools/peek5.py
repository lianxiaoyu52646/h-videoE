from pathlib import Path
print("--- count_vocab ---")
t = Path(r"D:\lian\praPro\h-videoE\app\crud.py").read_text(encoding="utf-8")
print("count_vocab" in t, "list_vocab_page" in t)
print("--- vocabulary endpoints ---")
v = Path(r"D:\lian\praPro\h-videoE\app\routers\vocabulary.py").read_text(encoding="utf-8")
for s in ["/api/vocab/study-feed", "/api/vocab/study-cursor", "/api/vocab/study-star", "import json"]:
    print(s, s in v)
print("--- index cache ---")
idx = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html").read_text(encoding="utf-8")
print(idx)
print("--- delete_vocab ---")
i = t.find("def delete_vocab_card")
print(t[i:i+400] if i>=0 else "missing")
