from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
lines = p.read_text(encoding="utf-8").splitlines()
print("\n".join(f"{i+1}|{lines[i]}" for i in range(17, 35)))
