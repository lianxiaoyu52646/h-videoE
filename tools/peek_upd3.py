from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
idx = 0
n = 0
while True:
    i = js.find("checkUpdateBtn", idx)
    if i < 0: break
    n += 1
    print("--- hit", n, i)
    print(js[i:i+250])
    idx = i+12
print("total", n)
