from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\main.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i in range(225, 280):
    print(f"{i+1}|{lines[i]}")
