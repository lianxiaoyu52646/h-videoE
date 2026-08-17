from pathlib import Path
html = Path(r"D:\lian\praPro\h-videoE\app\static\vocab.html").read_text(encoding="utf-8")
print("全部生词" in html, "vocabGrid" in html, "生词书" in html)
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
print("warehouse", "warehouse" in js)
print("生词本 · 全部", "生词本 · 全部" in js)
print("#vocab-book", "#vocab-book" in js)
