from pathlib import Path
root = Path(r"D:\lian\praPro\h-videoE")
for p in (root/"app").rglob("*.py"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    if "/tts" in t or "def tts" in t or "dictvoice" in t:
        print("FILE", p)
        for i,line in enumerate(t.splitlines(),1):
            if "tts" in line.lower() or "dictvoice" in line.lower() or "speech" in line.lower():
                print(f"  {i}:{line.strip()[:140]}")
