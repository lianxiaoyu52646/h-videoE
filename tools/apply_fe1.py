from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")
old = """  async function startStudy(wordbookId) {
    teardownStudyObservers();
    const localCursor = readLocalStudyCursor(wordbookId);
    writeLastStudyBook(wordbookId);
    state.study = {
      wordbookId,
      name: '',
"""
if old not in t:
    raise SystemExit("startStudy head missing")
new = r"""  function studyFeedBase(s) {
    return s.isVocabBook ? '/api/vocab/study-feed' : `/api/wordbooks/${s.wordbookId}/study-feed`;
  }
  function studyCursorPath(s) {
    return s.isVocabBook ? '/api/vocab/study-cursor' : `/api/wordbooks/${s.wordbookId}/study-cursor`;
  }
  function studyStarPath(s) {
    return s.isVocabBook ? '/api/vocab/study-star' : `/api/wordbooks/${s.wordbookId}/study-star`;
  }

  async function exitStudy() {
    const s = state.study;
    const wasVocab = !!s?.isVocabBook;
    if (s) {
      await saveStudyCursor(true);
      if (!wasVocab) patchBookProgressFromStudy();
      if (!wasVocab) writeLastStudyBook(s.wordbookId);
      if (s.wordbookId != null && s.lastSavedCursor != null) {
        writeLocalStudyCursor(s.wordbookId, s.lastSavedCursor);
      }
    }
    teardownStudyObservers();
    state.study = null;
    if (wasVocab) {
      setTab('vocab');
      return;
    }
    renderBooks();
    loadBooks().catch(() => {});
  }

  function renderStudySkeleton() {
    const root = $('#view-books');
    if (!root || !state.study) return;
    const s = state.study;
    root.innerHTML = `
      <div class="study-top">
        <button class="study-back" id="exitStudy" type="button" aria-label="back">` + "\u2190" + `</button>
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
      name: isVocabBook ? '\u751f\u8bcd\u4e66' : '',
"""
t = t.replace(old, new, 1)
old2 = "    await loadStudyPage('resume');\n  }"
new2 = "    renderStudySkeleton();\n    await loadStudyPage('resume');\n  }"
if old2 not in t:
    raise SystemExit("startStudy tail missing")
t = t.replace(old2, new2, 1)
p.write_text(t, encoding="utf-8")
print("startStudy ok")
