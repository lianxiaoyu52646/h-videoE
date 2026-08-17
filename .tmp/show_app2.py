from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
lines = p.read_text(encoding="utf-8").splitlines()
for i in range(1985, 2080):
    print(f"{i+1}|{lines[i]}")
