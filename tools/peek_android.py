from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\ui.js")
lines = p.read_text(encoding="utf-8").splitlines()
print("total", len(lines), "size", p.stat().st_size)
for i, line in enumerate(lines):
    if any(k in line for k in ["今日练习", "生词本", "renderVocab", "warehouse", "vocabGrid", "生词书", "reviewKnow"]):
        print(f"{i+1}:{line[:160]}")
