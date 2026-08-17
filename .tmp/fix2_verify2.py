from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("function prefetchVocabStudy")
print(js[i:i+900])
print("---css---")
css = Path(r"D:\lian\praPro\h-videoE\app\static\css\mobile.css").read_text(encoding="utf-8")
for needle in [".study-top {", ".study-top.is-away", ".study-list {", "is-study"]:
    j = css.find(needle)
    print(css[j:j+220])
    print("----")
print("---review.py---")
print(Path(r"D:\lian\praPro\h-videoE\app\routers\review.py").read_text(encoding="utf-8"))
