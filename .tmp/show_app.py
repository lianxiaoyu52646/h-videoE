from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
lines = p.read_text(encoding="utf-8").splitlines()
for i,l in enumerate(lines):
    if "paintDueCardFast" in l or "reviewDueCard" in l or "flash-card" in l or "STUDY_PAGE_SIZE" in l or "STUDY_DOM_WINDOW" in l or "slice(0, 2)" in l or "recommendations?limit" in l:
        print(f"{i+1}|{l}")
