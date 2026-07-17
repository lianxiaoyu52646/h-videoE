import httpx
import time

r = httpx.post('http://127.0.0.1:8000/api/videos', json={'url': 'https://www.bilibili.com/video/BV1z7411P7xb?p=2'}, timeout=30)
vid = r.json()['id']
print('video id:', vid)

t0 = time.time()
r2 = httpx.get(f'http://127.0.0.1:8000/api/videos/{vid}/subtitles', timeout=600)
t1 = time.time()
print(f'status: {r2.status_code} ({t1-t0:.1f}s)')

subs = r2.json()
print(f'subtitle count: {len(subs)}')
print('first 5:')
for s in subs[:5]:
    t = s.get("translation", "")
    print(f'  [{s["start"]:.1f}-{s["end"]:.1f}] {s["text"][:60]} => {t[:40]}')
