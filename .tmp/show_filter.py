from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
lines = p.read_text(encoding="utf-8").splitlines()
for i,l in enumerate(lines):
    if "getFilterParam" in l or "recommendations" in l:
        print(f"{i+1}|{l}")
