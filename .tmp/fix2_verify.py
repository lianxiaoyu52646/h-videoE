from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
keys = [
    "renderStudySkeleton",
    "rememberStudyCache",
    "openVocabBook",
    "reviewDueCard",
    "swapStudyRowsInPlace",
    "is-study",
    "skeleton-row",
    "studyChromeReady",
    "applyStudyCache",
]
for k in keys:
    print(f"{k}: {js.count(k)}")
# dump reviewDueCard and startStudy snippets
lines = js.splitlines()
for name in ["function reviewDueCard", "function openVocabBook", "async function startStudy", "function scrollToResumeWord", "const chromeReady"]:
    for i,l in enumerate(lines):
        if name in l:
            print(f"\n===== {name} @ {i+1} =====")
            for j in range(i, min(len(lines), i+45)):
                print(f"{j+1:5}|{lines[j]}")
            break
