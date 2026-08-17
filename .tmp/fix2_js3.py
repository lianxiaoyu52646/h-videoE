from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = p.read_text(encoding="utf-8")
old = """  async function loadVocab() {
    state.due = await api('/api/recommendations?limit=24');
  }
"""
new = """  async function loadVocab() {
    state.due = await api('/api/recommendations?limit=24');
    prefetchVocabStudy();
  }

  function prefetchVocabStudy() {
    if (state.study?.isVocabBook) return;
    const local = readLocalStudyCursor('vocab');
    let url = '/api/vocab/study-feed?limit=' + STUDY_PAGE_SIZE;
    if (local != null && Number.isFinite(local) && local >= 0) url += '&offset=' + Math.floor(local);
    api(url).then((data) => {
      if (!data || !Array.isArray(data.items) || !data.items.length) return;
      const offset = Number(data.offset || 0);
      rememberStudyCache({
        wordbookId: 'vocab',
        items: data.items,
        starred: new Set((data.items || []).filter((it) => it.starred).map((it) => it.id)),
        progress: data.progress || null,
        total: Number(data.total || 0),
        name: data.name || '\\u751f\\u8bcd\\u4e66',
        startOffset: offset,
        nextOffset: offset + data.items.length,
        hasMoreBefore: !!data.has_more_before,
        hasMoreAfter: data.has_more_after !== false,
      });
    }).catch(() => {});
  }
"""
if js.count(old) != 1:
    raise SystemExit('loadVocab not unique: %s' % js.count(old))
p.write_text(js.replace(old, new, 1), encoding="utf-8")
print("patched loadVocab prefetch")
