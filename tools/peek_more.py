from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
for k in ["m-list-item", "data-remove-vocab", "view-vocab", "生词本 ·", "全部 ("]:
    print(k, js.count(k))
print("--- android assets ---")
assets = Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets")
for p in sorted(assets.rglob("*")):
    if p.is_file() and p.suffix in {".html", ".js"}:
        print(p.relative_to(assets), p.stat().st_size)
print("--- vocab.html section ---")
html = Path(r"D:\lian\praPro\h-videoE\app\static\vocab.html").read_text(encoding="utf-8")
print(html)
