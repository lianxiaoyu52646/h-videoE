from pathlib import Path

# mobile: open 生词书 from hash
js_path = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = js_path.read_text(encoding="utf-8")
old = """    fetchAppVersion().catch(() => {});
    refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    setTab('read');
  }
  boot();
"""
new = """    fetchAppVersion().catch(() => {});
    refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    if (location.hash === '#vocab-book') openVocabBook();
    else setTab('read');
  }
  boot();
"""
if old not in js:
    raise SystemExit("boot tail missing")
js_path.write_text(js.replace(old, new, 1), encoding="utf-8")
print("boot hash ok")

idx = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html")
t = idx.read_text(encoding="utf-8")
t = t.replace("v=20260817.1", "v=20260817.2")
idx.write_text(t, encoding="utf-8")
print("cache", t.count("20260817.2"))

# android: drop full list under vocab page
ui = Path(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\ui.js")
u = ui.read_text(encoding="utf-8")
old = """      <div id="vocabGrid" class="vocab-grid"></div>
      
      <div class="card">
        <h3>📚 复习推荐</h3>
"""
new = """      <div class="card">
        <h3>📚 复习推荐</h3>
"""
if old not in u:
    raise SystemExit("android grid missing")
u = u.replace(old, new, 1)
old = """  const grid = document.getElementById('vocabGrid');
  const stats = document.getElementById('vocabStats');
  if (!grid || !stats) return;
  
  try {
    const items = await getVocab();
    renderVocabList(items);
    renderVocabStats(items);
    renderReview(items);
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
"""
new = """  const stats = document.getElementById('vocabStats');
  if (!stats) return;
  
  try {
    const items = await getVocab();
    renderVocabStats(items);
    renderReview(items);
  } catch (e) {
    stats.textContent = '加载失败';
  }
"""
if old not in u:
    raise SystemExit("android loadVocab missing")
ui.write_text(u.replace(old, new, 1), encoding="utf-8")
print("android ok")
