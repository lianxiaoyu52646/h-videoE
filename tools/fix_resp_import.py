from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\main.py")
t = p.read_text(encoding="utf-8")
old = "from fastapi.responses import FileResponse, JSONResponse, RedirectResponse"
new = "from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response"
if old not in t:
    raise SystemExit("import line missing")
if "RedirectResponse, Response" in t:
    print("already has Response")
else:
    p.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("import patched")
