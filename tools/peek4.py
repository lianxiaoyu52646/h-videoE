from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
i = js.find("async function startStudy")
print(js[i:i+1200])
print("==== state.study tail ====")
j = js.find("renderStudySkeleton();\n    await loadStudyPage")
print("skeleton call", j)
print("==== node check ====")
