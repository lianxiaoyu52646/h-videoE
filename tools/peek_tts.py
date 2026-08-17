from pathlib import Path
import re
html = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html").read_text(encoding="utf-8")
js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
print("cache_hits", html.count("20260817.3"), html.count("20260817.4"))
print("appjs", re.findall(r"app\.js\?v=[^\"']+", html))
print("unlockTts", "unlockTts" in js)
print("speakWord", js.count("function speakWord"))
print("rate", "1.08" in js)
print("prefetch", "prefetchSpeak" in js or "prefetch" in js.lower())
