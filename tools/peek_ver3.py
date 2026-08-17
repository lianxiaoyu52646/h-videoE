from pathlib import Path
main = Path(r"D:\lian\praPro\h-videoE\app\main.py").read_text(encoding="utf-8")
i = main.find("@app.get(\"/api/app-version\"")
if i < 0:
    i = main.find("api/app-version")
print("idx", i)
print(main[i:i+600])
print("====api fn====")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("async function api(")
print(js[i:i+800])
