import json
from pathlib import Path

cat = json.loads(Path("app/assets/curated/wordbook_catalog.json").read_text(encoding="utf-8"))
# KyleBing README published counts (txt version, full)
KYLEBING_TXT = {
    "chuzhong_kylebing": 3223,
    "gaozhong_kylebing": 6008,
    "cet4_kylebing": 7508,
    "cet6_kylebing": 5651,
    "kaoyan_kylebing": 9602,
    "toefl_kylebing": 13477,
    "sat_kylebing": 8887,
}
for c in cat:
    key = c["key"]
    local = c["entry_count"]
    off = KYLEBING_TXT.get(key)
    if off:
        print(f"{key:22} local={local:>6}  kylebing_txt={off:>6}  {local/off*100:5.1f}%")
    else:
        print(f"{key:22} local={local:>6}  kylebing_txt= n/a")
