from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\database.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i in range(240, len(lines)):
    print(f"{i+1}|{lines[i]}")
