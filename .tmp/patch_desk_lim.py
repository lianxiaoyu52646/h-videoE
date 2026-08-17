from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
text = p.read_text(encoding="utf-8")
old = "    reviewQueue = await api(`/api/recommendations${getFilterParam()}`);"
new = "    reviewQueue = await api(`/api/recommendations${getFilterParam()}${currentFilter ? '&' : '?'}limit=80`);"
n = text.count(old)
if n != 1:
    raise SystemExit(f"count={n}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("ok desktop limit=80")
