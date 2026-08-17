from pathlib import Path
print("=== android index ===")
print(Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\index.html").read_text(encoding="utf-8"))
print("=== android app.js ===")
print(Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\app.js").read_text(encoding="utf-8")[:2500])
print("=== m-list-item context ===")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("m-list-item")
print(js[i-200:i+200])
