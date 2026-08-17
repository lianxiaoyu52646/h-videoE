from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("function renderVocab()")
print(js[i:i+2200])
print("==== warehouse/全部 ====")
for key in ["warehouse", "生词本 · 全部", "vocabGrid", "全部单词"]:
    print(key, js.count(key))
