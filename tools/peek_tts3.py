from pathlib import Path
for rel in [
    r"app\static\js\vocab.js",
    r"app\static\js\wordbook-detail.js",
    r"app\static\js\ui.js",
    r"android\app\src\main\assets\js\ui.js",
]:
    p = Path(r"D:\lian\praPro\h-videoE") / rel
    if not p.exists():
        print("MISS", rel)
        continue
    text = p.read_text(encoding="utf-8")
    print("====", rel)
    for i,line in enumerate(text.splitlines(),1):
        if "function speak" in line or "speechSynthesis" in line or "AndroidDictionary" in line:
            print(f"  {i}:{line.strip()[:140]}")
