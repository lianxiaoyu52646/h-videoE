from pathlib import Path
import json
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json")
t = p.read_text(encoding="utf-8").replace("}\\n", "}\n").replace("}\\n", "}\n")
if t.endswith("}\\n"):
    t = t[:-2] + "\n"
# strip accidental trailing backslash-n
if t.rstrip().endswith("}"):
    # find last }
    t = t[:t.rfind("}")+1] + "\n"
data = json.loads(t)
data["web_content_version"] = "20260817.6"
data["notes"] = "检测最新版本会立刻显示服务器版本号"
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(data, ensure_ascii=False, indent=2))
print("ok")
