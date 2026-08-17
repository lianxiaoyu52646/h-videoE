from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("当前网页")
print(js[i-800:i+900])
print("====bind====")
i = js.find("checkUpdateBtn")
print(js[i-200:i+500])
