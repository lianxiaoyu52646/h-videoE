from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json")
print(p.read_text(encoding="utf-8"))
print("---index---")
html = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html").read_text(encoding="utf-8")
import re
print(re.findall(r"\?v=[0-9.]+", html)[:8])
print("---bump---")
bp = Path(r"D:\lian\praPro\h-videoE\tools\bump_cache.py")
print(bp.read_text(encoding="utf-8") if bp.exists() else "no bump_cache")
