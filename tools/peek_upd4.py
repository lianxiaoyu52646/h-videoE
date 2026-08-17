from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
idx = 0
while True:
    i = js.find("checkForUpdate(", idx)
    if i < 0: break
    print(js[i:i+80].replace("\n"," "))
    idx = i+10
print("fetchAppVersion calls")
idx = 0
while True:
    i = js.find("fetchAppVersion(", idx)
    if i < 0: break
    print(js[max(0,i-60):i+40].replace("\n"," | "))
    idx = i+10
