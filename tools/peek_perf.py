from pathlib import Path
import json, re
root = Path(r"D:\lian\praPro\h-videoE")
html = (root/"app/static/m/index.html").read_text(encoding="utf-8")
ver = json.loads((root/"app/static/m/app-version.json").read_text(encoding="utf-8"))
js = (root/"app/static/m/app.js").read_text(encoding="utf-8")
print("html", re.findall(r"\?v=[\d.]+", html)[:3])
print("json", ver.get("web_content_version"))
print("optimistic", "paintDueCardFast" in js)
print("pageSize", "STUDY_PAGE_SIZE" in js)
print("reviewBusy", "reviewBusy" in js)
