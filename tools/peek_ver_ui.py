from pathlib import Path
html = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html").read_text(encoding="utf-8")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
raw = Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json").read_bytes()
print("html5", html.count("20260817.5"), "html6", html.count("20260817.6"), "html4", html.count("20260817.4"))
print("json file", raw.decode("utf-8")[-80:])
print("paint", "function paintMineVersion" in js)
print("mineWebVer", js.count("mineWebVer"))
print("toast", "已是最新版本 " in js)
