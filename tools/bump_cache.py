from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html")
t = p.read_text(encoding="utf-8")
t = t.replace("20260817.3", "20260817.4")
p.write_text(t, encoding="utf-8")
print("bumped", t.count("20260817.4"))
