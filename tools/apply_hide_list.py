from pathlib import Path

html_path = Path(r"D:\lian\praPro\h-videoE\app\static\vocab.html")
html = html_path.read_text(encoding="utf-8")
old = """    <section class="panel">
      <h2>🧠 今日复习</h2>
      <div id="reviewArea"></div>
    </section>
"""
new = """    <section class="panel">
      <div class="filter-row" style="align-items:center;justify-content:space-between;gap:12px;">
        <h2 style="margin:0;">🧠 今日复习</h2>
        <a class="btn-primary" href="/app#vocab-book">生词书</a>
      </div>
      <div id="reviewArea"></div>
    </section>
"""
if old not in html:
    raise SystemExit("review section missing")
html = html.replace(old, new, 1)
old2 = """    <section class="panel">
      <h2>全部生词</h2>
      <div id="vocabGrid" class="vocab-grid"></div>
    </section>
"""
if old2 not in html:
    raise SystemExit("grid section missing")
html = html.replace(old2, "", 1)
html_path.write_text(html, encoding="utf-8")
print("vocab.html ok")

js_path = Path(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
js = js_path.read_text(encoding="utf-8")
old = """async function loadVocab() {
  try {
    const items = await api(`/api/vocab${getFilterParam()}`);
    renderVocab(items);
    renderStats(items);
  } catch (e) {
    vocabGrid.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}
"""
new = """async function loadVocab() {
  try {
    const items = await api(`/api/vocab${getFilterParam()}`);
    renderStats(items);
  } catch (e) {
    if (vocabStats) vocabStats.textContent = "加载失败";
  }
}
"""
if old not in js:
    raise SystemExit("loadVocab missing")
js = js.replace(old, new, 1)
js_path.write_text(js, encoding="utf-8")
print("vocab.js ok")
