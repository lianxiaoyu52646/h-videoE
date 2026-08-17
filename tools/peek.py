from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")

# fix skeleton arrow if broken
bad = '''aria-label="back">` + "\\u2190" + `</button>'''
# also the non-escaped version that was written
idx = t.find("renderStudySkeleton")
print("skeleton idx", idx)
print(t[idx:idx+900])
