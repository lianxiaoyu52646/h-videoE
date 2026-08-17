from pathlib import Path
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
needle = "/api/wordbooks/${s.wordbookId}/study-feed"
i = js.find(needle)
print("idx", i)
print(js[i-200:i+180])
print("---vocab.py compile---")
import py_compile
py_compile.compile(r"D:\lian\praPro\h-videoE\app\crud.py", doraise=True)
py_compile.compile(r"D:\lian\praPro\h-videoE\app\routers\vocabulary.py", doraise=True)
print("py ok")
