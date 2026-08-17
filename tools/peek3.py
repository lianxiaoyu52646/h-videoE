from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("function renderVocab()")
print(js[i:i+1800])
print("==== reviewDueCard ====")
j = js.find("async function reviewDueCard")
print("count", js.count("async function reviewDueCard"))
print(js[j:j+900])
print("==== www ====")
www = Path(r"D:\lian\praPro\h-videoE\mobile\www")
if www.exists():
    for p in www.rglob("app.js"):
        print(p, p.stat().st_size)
