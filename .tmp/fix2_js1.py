# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = p.read_text(encoding="utf-8")
n = 0

def repl(old, new, label):
    global js, n
    c = js.count(old)
    if c != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, found {c}")
    js = js.replace(old, new, 1)
    n += 1
    print("ok", label)

# 1) renderBooks: drop is-study when showing book list
repl(
"""  function renderBooks() {
    const root = $('#view-books');
    if (state.study) return renderStudy(root);
""",
"""  function renderBooks() {
    const root = $('#view-books');
    if (state.study) return renderStudy(root);
    root.classList.remove('is-study');
""",
"renderBooks is-study")

# 2) exitStudy: cache snapshot + remove is-study
repl(
"""  async function exitStudy() {
    const s = state.study;
    const wasVocab = !!s?.isVocabBook;
    if (s) {
      await saveStudyCursor(true);
""",
"""  async function exitStudy() {
    const s = state.study;
    const wasVocab = !!s?.isVocabBook;
    if (s) {
      rememberStudyCache(s);
      await saveStudyCursor(true);
""",
"exitStudy cache")

repl(
"""    teardownStudyObservers();
    state.study = null;
    if (wasVocab) {
      setTab('vocab');
      return;
    }
""",
"""    teardownStudyObservers();
    state.study = null;
    $('#view-books')?.classList.remove('is-study');
    if (wasVocab) {
      setTab('vocab');
      return;
    }
""",
"exitStudy remove is-study")

# 3) Replace skeleton + openVocabBook + startStudy with cache-first paint
old_block = """  function renderStudySkeleton() {
    const root = $('#view-books');
    if (!root || !state.study) return;
    const s = state.study;
    root.innerHTML = `
      <div class="study-top">
        <button class="study-back" id="exitStudy" type="button" aria-label="back">` + "\\u2190" + `</button>
        <div class="study-top-main">
          <div class="study-top-title">${escapeHtml(s.name || 'book')}</div>
          <div class="study-top-meta">...</div>
          <div class="progress-bar-wrap"><div class="progress-bar" style="width:0%"></div></div>
        </div>
      </div>
      <div id="studyList" class="study-list">
        ${Array.from({ length: 6 }).map(() => '<article class="study-row skeleton-row"></article>').join('')}
      </div>`;
    $('#exitStudy').onclick = () => { exitStudy(); };
  }

  function openVocabBook() {
    state.tab = 'books';
    $$('#tabNav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === 'books'));
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-books'));
    startStudy('vocab', { vocabBook: true }).catch((e) => toast(e.message || 'fail'));
  }

  async function startStudy(wordbookId, { vocabBook = false } = {}) {
    teardownStudyObservers();
    const isVocabBook = !!(vocabBook || wordbookId === 'vocab');
    const cursorKey = isVocabBook ? 'vocab' : wordbookId;
    const localCursor = readLocalStudyCursor(cursorKey);
    if (!isVocabBook) writeLastStudyBook(wordbookId);
    state.study = {
      wordbookId: cursorKey,
      isVocabBook,
      name: isVocabBook ? '\\u751f\\u8bcd\\u4e66' : '',
      items: [],
      starred: new Set(),
      progress: null,
      total: 0,
      loadingBefore: false,
      loadingAfter: false,
      hasMoreBefore: false,
      hasMoreAfter: true,
      startOffset: 0,
      nextOffset: 0,
      resumeTarget: localCursor != null ? localCursor : 0,
      observers: [],
      onScroll: null,
      cursorTimer: null,
      lastSavedCursor: localCursor,
      bootstrapped: false,
      feedSeq: 0,
      // Until user scrolls upward, do not auto-fetch earlier pages (was causing lag + jump).
      allowLoadBefore: false,
      lastScrollY: 0,
      localResumeOffset: localCursor,
      prefetchAfter: null,
      prefetching: false,
      serverCursorDirty: false,
    };
    renderStudySkeleton();
    await loadStudyPage('resume');
  }
"""

new_block = r"""  function studyCacheKey(wordbookId) {
    return 'wp_study_snap_' + String(wordbookId);
  }

  function readStudyCache(wordbookId) {
    try {
      const raw = sessionStorage.getItem(studyCacheKey(wordbookId));
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || !Array.isArray(data.items) || !data.items.length) return null;
      return data;
    } catch (_) {
      return null;
    }
  }

  function rememberStudyCache(s) {
    if (!s?.wordbookId || !Array.isArray(s.items) || !s.items.length) return;
    try {
      sessionStorage.setItem(studyCacheKey(s.wordbookId), JSON.stringify({
        items: s.items,
        starred: [...(s.starred || [])],
        progress: s.progress || null,
        total: s.total || 0,
        name: s.name || '',
        startOffset: s.startOffset || 0,
        nextOffset: s.nextOffset || 0,
        hasMoreBefore: !!s.hasMoreBefore,
        hasMoreAfter: s.hasMoreAfter !== false,
      }));
    } catch (_) {}
  }

  function applyStudyCache(s, cached) {
    if (!s || !cached?.items?.length) return false;
    s.items = cached.items.slice();
    s.starred = new Set(cached.starred || []);
    s.progress = cached.progress || s.progress;
    s.total = Number(cached.total || s.total || 0);
    if (cached.name) s.name = cached.name;
    s.startOffset = Number(cached.startOffset || 0);
    s.nextOffset = Number(cached.nextOffset || (s.startOffset + s.items.length));
    s.hasMoreBefore = !!cached.hasMoreBefore;
    s.hasMoreAfter = cached.hasMoreAfter !== false;
    s.bootstrapped = true;
    syncStudyBounds();
    return true;
  }

  function studyChromeReady() {
    return !!(state.study && $('#view-books .study-top') && $('#studyList'));
  }

  function swapStudyRowsInPlace() {
    const s = state.study;
    const list = $('#studyList');
    if (!s || !list) {
      const root = $('#view-books');
      if (root) renderStudy(root);
      return;
    }
    list.innerHTML = (s.items || []).map((it) => studyRowHtml(it)).join('');
    bindStudyStarButtons(list);
    updateStudyProgressUi();
    updateStudySentinels();
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
    if (jumpTo != null) setActiveStudyRow(jumpTo);
    rememberStudyCache(s);
  }

  function openVocabBook() {
    const booksView = $('#view-books');
    state.tab = 'books';
    $$('#tabNav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === 'books'));
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === 'view-books'));
    booksView?.classList.add('is-study');
    try { window.scrollTo(0, 0); } catch (_) {}
    startStudy('vocab', { vocabBook: true }).catch((e) => toast(e.message || 'fail'));
  }

  async function startStudy(wordbookId, { vocabBook = false } = {}) {
    teardownStudyObservers();
    const isVocabBook = !!(vocabBook || wordbookId === 'vocab');
    const cursorKey = isVocabBook ? 'vocab' : wordbookId;
    const localCursor = readLocalStudyCursor(cursorKey);
    if (!isVocabBook) writeLastStudyBook(wordbookId);
    const root = $('#view-books');
    root?.classList.add('is-study');
    try { window.scrollTo(0, 0); } catch (_) {}
    state.study = {
      wordbookId: cursorKey,
      isVocabBook,
      name: isVocabBook ? '\u751f\u8bcd\u4e66' : '',
      items: [],
      starred: new Set(),
      progress: null,
      total: 0,
      loadingBefore: false,
      loadingAfter: false,
      hasMoreBefore: false,
      hasMoreAfter: true,
      startOffset: 0,
      nextOffset: 0,
      resumeTarget: localCursor != null ? localCursor : 0,
      observers: [],
      onScroll: null,
      cursorTimer: null,
      lastSavedCursor: localCursor,
      bootstrapped: false,
      feedSeq: 0,
      // Until user scrolls upward, do not auto-fetch earlier pages (was causing lag + jump).
      allowLoadBefore: false,
      lastScrollY: 0,
      localResumeOffset: localCursor,
      prefetchAfter: null,
      prefetching: false,
      serverCursorDirty: false,
    };
    applyStudyCache(state.study, readStudyCache(cursorKey));
    if (root) renderStudy(root);
    await loadStudyPage('resume');
  }
"""

repl(old_block, new_block, "openVocabBook/startStudy cache-first")

print("partial ok, writing checkpoint")
p.write_text(js, encoding="utf-8")
print("wrote after first batch, replacements", n)
