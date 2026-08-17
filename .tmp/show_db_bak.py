from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\database.py.bak-20260817-perf")
lines = p.read_text(encoding="utf-8").splitlines()
# find init_db
for i,l in enumerate(lines):
    if "def init_db" in l:
        for j in range(i, min(i+20, len(lines))):
            print(f"{j+1}|{lines[j]}")
        break
