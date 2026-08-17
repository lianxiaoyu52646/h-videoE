from pathlib import Path
import json
import re

root = Path(r"D:\lian\praPro\h-videoE")

# 1) bump app-version.json
p = root / "app" / "static" / "m" / "app-version.json"
data = json.loads(p.read_text(encoding="utf-8"))
data["web_content_version"] = "20260817.4"
data["notes"] = "生词书独立页；喇叭点击立即发音"
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("json", data["web_content_version"])

# 2) Cache-Control on API
main_p = root / "app" / "main.py"
main = main_p.read_text(encoding="utf-8")
old = '''@app.get("/api/app-version", response_model=schemas.AppVersionRead)
def app_version():
    return _load_app_version()
'''
new = '''@app.get("/api/app-version", response_model=schemas.AppVersionRead)
def app_version(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return _load_app_version()
'''
if old not in main:
    raise SystemExit("app_version handler mismatch")
# ensure Response is imported
if "from fastapi" in main and "Response" not in main.split("from fastapi")[1].split("\n")[0]:
    # check existing imports
    pass
if re.search(r"from fastapi(?:\.responses)? import [^\n]*Response", main):
    print("Response already imported")
elif "from fastapi import" in main:
    main = re.sub(
        r"from fastapi import ([^\n]+)",
        lambda m: m.group(0) if "Response" in m.group(1) else "from fastapi import " + m.group(1) + ", Response",
        main,
        count=1,
    )
    print("added Response to fastapi import")
else:
    main = "from fastapi import Response\n" + main
    print("prepended Response import")
main = main.replace(old, new, 1)
main_p.write_text(main, encoding="utf-8")

# 3) client fetch no-store
js_p = root / "app" / "static" / "m" / "app.js"
js = js_p.read_text(encoding="utf-8")
old_js = "cachedAppVersion = await api('/api/app-version');"
new_js = "cachedAppVersion = await api('/api/app-version?_t=' + Date.now(), { cache: 'no-store' });"
if old_js not in js:
    raise SystemExit("fetchAppVersion line mismatch")
js = js.replace(old_js, new_js, 1)
js_p.write_text(js, encoding="utf-8")
print("js fetch patched")

# 4) bump_cache.py keeps both in sync
bump = r'''from pathlib import Path
import json
import re
from datetime import datetime

ROOT = Path(r"D:\lian\praPro\h-videoE")
VER = datetime.now().strftime("%Y%m%d")
# keep a daily bump: YYYYMMDD.N
html_p = ROOT / "app" / "static" / "m" / "index.html"
json_p = ROOT / "app" / "static" / "m" / "app-version.json"
html = html_p.read_text(encoding="utf-8")
m = re.search(r"\?v=(\d{8}\.\d+)", html)
cur = m.group(1) if m else "0"
date, _, n = cur.partition(".")
today = datetime.now().strftime("%Y%m%d")
if date == today:
    nxt = f"{today}.{int(n or 0) + 1}"
else:
    nxt = f"{today}.1"
html2 = re.sub(r"\?v=\d{8}\.\d+", f"?v={nxt}", html)
html_p.write_text(html2, encoding="utf-8")
data = json.loads(json_p.read_text(encoding="utf-8"))
data["web_content_version"] = nxt
json_p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("bumped", cur, "->", nxt)
'''
(root / "tools" / "bump_cache.py").write_text(bump, encoding="utf-8")
print("bump_cache rewritten")
