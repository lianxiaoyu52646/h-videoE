# -*- coding: utf-8 -*-
from pathlib import Path
import shutil

ROOT = Path(r"D:\lian\praPro\h-videoE")
TAG = "bak-20260817-fix2"

def backup(rel):
    src = ROOT / rel
    dst = Path(str(src) + "." + TAG)
    if not dst.exists():
        shutil.copy2(src, dst)
        print("backup", dst.name)
    else:
        print("backup exists", dst.name)

files = [
    "app/static/m/app.js",
    "app/static/m/index.html",
    "app/static/m/app-version.json",
    "app/static/css/mobile.css",
    "app/routers/review.py",
    "app/crud.py",
]
for f in files:
    backup(f)
print("backups done")
