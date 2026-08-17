from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
lines = p.read_text(encoding="utf-8").splitlines()
for i in range(2858, len(lines)):
    print(f"{i+1}|{lines[i].encode('unicode_escape').decode()}")
print("--- vocab.js speak ---")
v = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js").read_text(encoding="utf-8").splitlines()
for i in range(180, 205):
    print(f"{i+1}|{v[i]}")
