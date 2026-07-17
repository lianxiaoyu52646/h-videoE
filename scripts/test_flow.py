import httpx
import time

base = "http://127.0.0.1:8000"
r = httpx.get(base + "/api/videos")
print("list", r.status_code, len(r.json()))
for v in r.json():
    print(" ", v["id"], v["subtitle_status"], v["progress"], v["subtitle_count"], (v.get("title") or "")[:30])

url = "https://www.bilibili.com/video/BV1GJ411x7h7"
r = httpx.post(base + "/api/videos", json={"url": url})
print("add", r.status_code)
v = r.json()
vid = v["id"]
print("video", vid, v["subtitle_status"], (v.get("title") or "")[:40])

s = v
for i in range(25):
    time.sleep(2)
    s = httpx.get(base + f"/api/videos/{vid}").json()
    msg = (s.get("status_message") or "")[:50]
    print(f"  poll {i}: {s['subtitle_status']} {s['progress']}% subs={s['subtitle_count']} {msg}")
    if s["subtitle_status"] in ("done", "failed"):
        break

if s["subtitle_status"] == "done" and s["subtitle_count"] > 0:
    subs = httpx.get(base + f"/api/videos/{vid}/subtitles").json()
    print("subs count", len(subs))
    if subs:
        print("sample", subs[0])
