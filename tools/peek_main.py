from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\main.py")
print(p.read_text(encoding="utf-8")[1:2500])
print("==== routes ====")
lines = p.read_text(encoding="utf-8").splitlines()
for i,l in enumerate(lines[90:170], 91):
    print(f"{i}|{l}")
