from pathlib import Path
main = Path(r"D:\lian\praPro\h-videoE\app\main.py").read_text(encoding="utf-8")
print("===imports===")
for line in main.splitlines()[:40]:
    if "import" in line.lower() and ("fastapi" in line.lower() or "Response" in line):
        print(line)
print("===handler===")
i = main.find("api/app-version")
print(main[i-80:i+280])
print("===json===")
print(Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json").read_text(encoding="utf-8"))
print("===js fetch===")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("async function fetchAppVersion")
print(js[i:i+420])
