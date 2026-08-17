from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html")
t = p.read_text(encoding="utf-8")
t2 = t.replace("v=20260804.7", "v=20260817.1")
if t2 == t:
    raise SystemExit("version not found")
p.write_text(t2, encoding="utf-8")
print("cache bust", t2.count("20260817.1"))
