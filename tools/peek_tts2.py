from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
lines = p.read_text(encoding="utf-8").splitlines()
print("===== speak 356-430 =====")
for i in range(355, min(430, len(lines))):
    print(f"{i+1}|{lines[i]}")
print("===== click 2855-2889 =====")
for i in range(2854, min(2889, len(lines))):
    print(f"{i+1}|{lines[i]}")
