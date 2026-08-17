from pathlib import Path
root = Path(r"D:\lian\praPro\h-videoE")
for p in root.rglob("*"):
    if any(x in str(p) for x in [".venv","venv","node_modules","dist",".git"]):
        continue
    if p.suffix.lower() not in {".js", ".html", ".json"}:
        continue
    try:
        t = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if "serviceWorker" in t or "workbox" in t or "sw.js" in t:
        print("SW", p)
print("--- views css ---")
css = Path(r"D:\lian\praPro\h-videoE\app\static\css\mobile.css").read_text(encoding="utf-8")
for i,line in enumerate(css.splitlines(),1):
    if ".view" in line and ("display" in line or "{" in line or "active" in line):
        if i < 80 or "view" in line.lower():
            print(f"{i}:{line}")
