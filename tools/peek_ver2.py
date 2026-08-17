from pathlib import Path
import re

# main.py app-version endpoint
main = Path(r"D:\lian\praPro\h-videoE\app\main.py").read_text(encoding="utf-8")
idx = main.find("app-version")
print("main hits", main.count("app-version"))
print(main[max(0,idx-200):idx+800][:1200])
print("====APPJS====")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
for name in ["fetchAppVersion", "checkForUpdate", "localWebVersion", "wp_web_content_version"]:
    print(name, js.find(name))
i = js.find("async function fetchAppVersion")
if i < 0:
    i = js.find("function fetchAppVersion")
print("---fetch---")
print(js[i:i+700])
i2 = js.find("async function checkForUpdate")
print("---check---")
print(js[i2:i2+900])
