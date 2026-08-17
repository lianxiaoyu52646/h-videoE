from pathlib import Path
import json, py_compile

idx = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html").read_text(encoding="utf-8")
print("index versions:", [line.strip() for line in idx.splitlines() if "?v=" in line])
ver = json.loads(Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json").read_text(encoding="utf-8"))
print("app-version", ver["web_content_version"], "notes", ver.get("notes"))

files = [
    r"D:\lian\praPro\h-videoE\app\routers\review.py",
    r"D:\lian\praPro\h-videoE\app\routers\vocabulary.py",
    r"D:\lian\praPro\h-videoE\app\crud.py",
    r"D:\lian\praPro\h-videoE\app\services\wordbook_study.py",
    r"D:\lian\praPro\h-videoE\app\database.py",
    r"D:\lian\praPro\h-videoE\app\models.py",
]
for f in files:
    py_compile.compile(f, doraise=True)
    print("py_ok", Path(f).name)
print("compile done")
