from pathlib import Path

css_path = Path(r"D:\lian\praPro\h-videoE\app\static\css\mobile.css")
css = css_path.read_text(encoding="utf-8")
old = """.study-top {
  position: sticky;
  top: 58px;
  z-index: 12;
"""
new = """.study-top {
  position: sticky;
  top: 58px;
  z-index: 12;
  transition: opacity 0.22s ease, transform 0.22s ease;
"""
if old not in css:
    raise SystemExit("study-top missing")
css = css.replace(old, new, 1)
if ".study-top.is-away" not in css:
    css = css.replace(".study-top-title {", """.study-top.is-away {
  opacity: 0;
  transform: translateY(-12px);
  pointer-events: none;
}
.skeleton-row {
  min-height: 88px;
  border-radius: 18px;
  background: linear-gradient(90deg, #f3f3f6 25%, #ececf1 37%, #f3f3f6 63%);
  background-size: 400% 100%;
  animation: vocabSk 1.15s ease infinite;
}
@keyframes vocabSk {
  0% { background-position: 100% 0; }
  100% { background-position: 0 0; }
}
.m-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 8px;
}
.m-card-head h2 { margin: 0; }
.m-card-head .m-btn { flex: 0 0 auto; padding: 8px 14px; }
.study-top-title {""", 1)
css_path.write_text(css, encoding="utf-8")
print("css ok")

desk = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
t = desk.read_text(encoding="utf-8")
old = """      reviewIdx++;
      showAnswer = false;
      renderReview();
      await loadVocab();
"""
if old in t:
    desk.write_text(t.replace(old, """      reviewIdx++;
      showAnswer = false;
      renderReview();
""", 1), encoding="utf-8")
    print("desktop vocab.js ok")
else:
    print("desktop vocab.js skip")

js = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js").read_text(encoding="utf-8")
checks = [
    "openVocabBookBtn",
    "isVocabBook",
    "studyFeedBase",
    "is-away",
    "function renderVocab()",
    "state.reviewBusy",
    "const pageSize = 20",
]
for c in checks:
    print(c, js.count(c))
print("leftover study-feed hardcoded", js.count("/api/wordbooks/${s.wordbookId}/study-feed"))
