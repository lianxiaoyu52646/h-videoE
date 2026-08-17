from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
for name in ["function localWebVersion", "function rememberWebVersion", "async function checkForUpdate", "function renderMine", "checkUpdateBtn", "当前网页"]:
    print("====", name, js.find(name))

def dump(marker, n=1800):
    i = js.find(marker)
    print("\n#####", marker, i)
    print(js[i:i+n] if i>=0 else "MISSING")

dump("function localWebVersion", 400)
dump("function rememberWebVersion", 400)
dump("async function checkForUpdate", 2200)
dump("function renderMine", 2500)
