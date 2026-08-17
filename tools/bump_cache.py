from pathlib import Path
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
