from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
text = p.read_text(encoding="utf-8")

def one(label, old, new):
    global text
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label} count={n}")
    text = text.replace(old, new, 1)
    print("ok", label)

one(
    "dom_window",
    "  const STUDY_DOM_WINDOW = 40;",
    "  const STUDY_PAGE_SIZE = 12;\n  const STUDY_DOM_WINDOW = 24;",
)

one(
    "page_size_load",
    "    const pageSize = 20;\n    updateStudySentinels();",
    "    const pageSize = STUDY_PAGE_SIZE;\n    updateStudySentinels();",
)

one(
    "page_size_prefetch",
    "    s.prefetching = true;\n    const pageSize = 20;",
    "    s.prefetching = true;\n    const pageSize = STUDY_PAGE_SIZE;",
)

one(
    "append_rows",
    '''  function appendStudyRows(items) {
    const list = $('#studyList');
    if (!list || !items.length) return;
    const wrap = document.createElement('div');
    wrap.innerHTML = items.map((it) => studyRowHtml(it, { animate: false })).join('');
    [...wrap.children].forEach((n) => list.appendChild(n));
    bindStudyStarButtons(list);
    if (state.study?.activeOffset != null) setActiveStudyRow(state.study.activeOffset);
  }''',
    '''  function appendStudyRows(items) {
    const list = $('#studyList');
    if (!list || !items.length) return;
    list.insertAdjacentHTML('beforeend', items.map((it) => studyRowHtml(it, { animate: false })).join(''));
    bindStudyStarButtons(list);
    if (state.study?.activeOffset != null) setActiveStudyRow(state.study.activeOffset);
  }''',
)

one(
    "prepend_rows",
    '''  function prependStudyRows(items) {
    const list = $('#studyList');
    if (!list || !items.length) return;
    const height = document.documentElement.scrollHeight;
    const y = window.scrollY;
    const wrap = document.createElement('div');
    wrap.innerHTML = items.map((it) => studyRowHtml(it, { animate: false })).join('');
    const first = list.firstChild;
    [...wrap.children].forEach((n) => list.insertBefore(n, first));
    bindStudyStarButtons(list);
    window.scrollTo(0, y + (document.documentElement.scrollHeight - height));
    if (state.study?.activeOffset != null) setActiveStudyRow(state.study.activeOffset);
  }''',
    '''  function prependStudyRows(items) {
    const list = $('#studyList');
    if (!list || !items.length) return;
    const height = document.documentElement.scrollHeight;
    const y = window.scrollY;
    list.insertAdjacentHTML('afterbegin', items.map((it) => studyRowHtml(it, { animate: false })).join(''));
    bindStudyStarButtons(list);
    window.scrollTo(0, y + (document.documentElement.scrollHeight - height));
    if (state.study?.activeOffset != null) setActiveStudyRow(state.study.activeOffset);
  }''',
)

one(
    "trim_dom",
    '''    if (direction === 'after') {
      // Scrolling down: drop oldest rows from top, preserve scroll position.
      const height = document.documentElement.scrollHeight;
      const y = window.scrollY;
      const removed = s.items.splice(0, drop);
      removed.forEach((it) => {
        const el = list.querySelector(`.study-row[data-offset="${it.offset}"]`);
        if (el) el.remove();
      });
      s.startOffset = Number(s.items[0]?.offset ?? s.startOffset);
      window.scrollTo(0, Math.max(0, y - (height - document.documentElement.scrollHeight)));
    } else if (direction === 'before') {
      // Scrolling up: drop newest rows from bottom.
      const removed = s.items.splice(s.items.length - drop, drop);
      removed.forEach((it) => {
        const el = list.querySelector(`.study-row[data-offset="${it.offset}"]`);
        if (el) el.remove();
      });
      s.nextOffset = Number(s.items[s.items.length - 1]?.offset ?? s.nextOffset) + 1;
    }''',
    '''    if (direction === 'after') {
      const height = document.documentElement.scrollHeight;
      const y = window.scrollY;
      s.items.splice(0, drop);
      const firstKeep = s.items[0]?.offset;
      while (list.firstElementChild) {
        const el = list.firstElementChild;
        if (el.classList.contains('study-row') && Number(el.dataset.offset) === Number(firstKeep)) break;
        el.remove();
      }
      s.startOffset = Number(s.items[0]?.offset ?? s.startOffset);
      window.scrollTo(0, Math.max(0, y - (height - document.documentElement.scrollHeight)));
    } else if (direction === 'before') {
      s.items.splice(s.items.length - drop, drop);
      const lastKeep = s.items[s.items.length - 1]?.offset;
      while (list.lastElementChild) {
        const el = list.lastElementChild;
        if (el.classList.contains('study-row') && Number(el.dataset.offset) === Number(lastKeep)) break;
        el.remove();
      }
      s.nextOffset = Number(s.items[s.items.length - 1]?.offset ?? s.nextOffset) + 1;
    }''',
)

one(
    "resume_no_second_fetch",
    '''      let resumeKeep = null;
      if (mode === 'resume') {
        const serverResume = Number(data.resume_offset ?? data.progress?.cursor ?? 0);
        const local = s.localResumeOffset != null ? Math.floor(s.localResumeOffset) : 0;
        let target = Math.max(serverResume, local);
        const totalHint = Number(data.total || 0);
        if (totalHint) target = Math.max(0, Math.min(target, totalHint - 1));
        const pageStart = Number(data.offset ?? 0);
        const pageEnd = pageStart + (data.items || []).length;
        if ((data.items || []).length && (target < pageStart || target >= pageEnd)) {
          data = await api(
            `${studyFeedBase(s)}?limit=${pageSize}&offset=${target}`
          );
          if (state.study !== s || seq !== s.feedSeq) return;
        }
        resumeKeep = target;
        writeLocalStudyCursor(s.wordbookId, target);
      }''',
    '''      let resumeKeep = null;
      if (mode === 'resume') {
        const pageStart = Number(data.offset ?? 0);
        const local = s.localResumeOffset != null ? Math.floor(s.localResumeOffset) : pageStart;
        const serverResume = Number(data.resume_offset ?? data.progress?.cursor ?? pageStart);
        let target = Math.max(serverResume, local);
        const totalHint = Number(data.total || 0);
        if (totalHint) target = Math.max(0, Math.min(target, totalHint - 1));
        const pageEnd = pageStart + (data.items || []).length;
        // First paint with this page — do not block on a second GET.
        if (!(data.items || []).length || target < pageStart || target >= pageEnd) {
          target = pageStart;
        }
        resumeKeep = target;
        writeLocalStudyCursor(s.wordbookId, target);
      }''',
)

one(
    "prefetch_tts_2",
    "    (s.items || []).slice(0, 10).forEach((it) => { if (it?.word) prefetchSpeak(it.word); });",
    "    (s.items || []).slice(0, 2).forEach((it) => { if (it?.word) prefetchSpeak(it.word); });",
)

one(
    "load_vocab_limit",
    "    state.due = await api('/api/recommendations');",
    "    state.due = await api('/api/recommendations?limit=24');",
)

p.write_text(text, encoding="utf-8")
print("app.js batch1 done")
