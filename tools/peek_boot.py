from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("async function boot()")
print(js[i:i+900])
print("--- routes ---")
# find /app and /vocab routes
for p in Path(r"D:\lian\praPro\h-videoE\app").rglob("*.py"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    if "/app" in t or "vocab.html" in t:
        for n,line in enumerate(t.splitlines(),1):
            if "/app" in line or "vocab.html" in line or "FileResponse" in line:
                print(p.name, n, line.strip()[:140])
