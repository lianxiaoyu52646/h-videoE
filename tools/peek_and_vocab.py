from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\ui.js")
lines = p.read_text(encoding="utf-8").splitlines()
for i in range(1698, 1820):
    print(f"{i+1}|{lines[i]}")
