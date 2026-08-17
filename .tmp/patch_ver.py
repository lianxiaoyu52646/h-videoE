from pathlib import Path

# versions
idx = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html")
text = idx.read_text(encoding="utf-8")
n = text.count("20260817.4")
if n < 1:
    raise SystemExit(f"index version count={n}")
idx.write_text(text.replace("20260817.4", "20260817.5"), encoding="utf-8")
print("index.html bumped", n, "occurrences")

ver = Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json")
vtext = ver.read_text(encoding="utf-8")
if '"web_content_version": "20260817.4"' not in vtext:
    raise SystemExit("app-version web_content_version not 20260817.4")
vtext = vtext.replace('"web_content_version": "20260817.4"', '"web_content_version": "20260817.5"', 1)
vtext = vtext.replace(
    '"notes": "\\u751f\\u8bcd\\u4e66\\u72ec\\u7acb\\u9875\\uff1b\\u5587\\u53ed\\u70b9\\u51fb\\u7acb\\u5373\\u53d1\\u97f3"',
    '"notes": "vocab/study perf: optimistic review, lean feed, smaller DOM"',
)
# notes is Chinese in the file, replace more loosely
import json
data = json.loads(Path(r"D:\lian\praPro\h-videoE\app\static\m\app-version.json").read_text(encoding="utf-8"))
# file not yet written with new notes; load current then write
data = json.loads(ver.read_text(encoding="utf-8"))
data["web_content_version"] = "20260817.5"
data["notes"] = "vocab/study perf: optimistic review, lean feed, smaller DOM"
ver.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("app-version.json", data["web_content_version"])

# desktop vocab.js optimistic review
vp = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
vt = vp.read_text(encoding="utf-8")
old = '''  reviewArea.querySelectorAll('.review-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const rating = parseInt(btn.dataset.rating);
      await api('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vocab_id: card.id, rating }),
      });
      reviewIdx++;
      showAnswer = false;
      renderReview();
    });
  });
'''
new = '''  reviewArea.querySelectorAll('.review-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const rating = parseInt(btn.dataset.rating);
      api('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vocab_id: card.id, rating }),
      }).catch(() => {});
      reviewIdx++;
      showAnswer = false;
      renderReview();
    });
  });
'''
n = vt.count(old)
if n != 1:
    raise SystemExit(f"desktop review count={n}")
vp.write_text(vt.replace(old, new, 1), encoding="utf-8")
print("ok desktop vocab.js")
