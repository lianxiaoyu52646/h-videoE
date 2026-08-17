from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
lines = p.read_text(encoding="utf-8").splitlines()
print("\n".join(f"{i+1}|{lines[i]}" for i in range(2016, 2042)))
print("--- review.py ---")
print(Path(r"D:\lian\praPro\h-videoE\app\routers\review.py").read_text(encoding="utf-8"))
