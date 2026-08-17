from pathlib import Path
root = Path(r"D:\lian\praPro\h-videoE")
keys = ("生词本 · 全部", "全部单词", "vocabGrid", "warehouse", "id=\"vocabGrid\"")
for p in root.rglob("*"):
    if any(x in str(p) for x in [".venv", "venv", "node_modules", "dist", "build", ".git", ".bak"]):
        continue
    if p.suffix.lower() not in {".js", ".html", ".css", ".vue", ".tsx", ".ts"}:
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        continue
    hits = []
    for i, line in enumerate(t.splitlines(), 1):
        if any(k in line for k in keys):
            hits.append(f"{i}:{line.strip()[:140]}")
    if hits:
        print("FILE", p)
        print("\n".join(hits[:30]))
        print("---")
