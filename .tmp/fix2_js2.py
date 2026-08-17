# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = p.read_text(encoding="utf-8")
n = 0

def repl(old, new, label):
    global js, n
    c = js.count(old)
    if c != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, found {c}\n--- snippet ---\n{old[:180]}")
    js = js.replace(old, new, 1)
    n += 1
    print("ok", label)

repl(
"""      const fresh = applyStudyPage(data, mode === 'resume' ? 'resume' : mode);

      if (mode === 'resume' || !s.bootstrapped) {
        if (mode === 'resume' && resumeKeep != null) {
          s.resumeTarget = s.total
            ? Math.max(0, Math.min(resumeKeep, s.total - 1))
            : resumeKeep;
          s.lastSavedCursor = s.resumeTarget;
        }
        s.bootstrapped = true;
        s.allowLoadBefore = false;
        renderBooks();
        schedulePrefetchAfter();
        return;
      }
""",
"""      const chromeReady = studyChromeReady();
      const prevSig = chromeReady ? (s.items || []).map((it) => `${it.id}:${it.offset}`).join(',') : '';
      const fresh = applyStudyPage(data, mode === 'resume' ? 'resume' : mode);

      if (mode === 'resume' || !s.bootstrapped) {
        if (mode === 'resume' && resumeKeep != null) {
          s.resumeTarget = s.total
            ? Math.max(0, Math.min(resumeKeep, s.total - 1))
            : resumeKeep;
          s.lastSavedCursor = s.resumeTarget;
        }
        s.bootstrapped = true;
        s.allowLoadBefore = false;
        rememberStudyCache(s);
        const nextSig = (s.items || []).map((it) => `${it.id}:${it.offset}`).join(',');
        if (chromeReady) {
          if (prevSig !== nextSig) swapStudyRowsInPlace();
          else {
            updateStudyProgressUi();
            updateStudySentinels();
          }
        } else {
          renderBooks();
        }
        schedulePrefetchAfter();
        return;
      }
""",
"loadStudyPage in-place resume")

repl(
"""    s.lastScrollY = window.scrollY;
    let scrollRaf = 0;
    s.onScroll = () => {
""",
"""    s.lastScrollY = window.scrollY;
    $('.study-top')?.classList.remove('is-away');
    let scrollRaf = 0;
    s.onScroll = () => {
""",
"observers no is-away on attach")

repl(
"""  function scrollToResumeWord() {
    const s = state.study;
    if (!s) return;
    const target = Number(s.resumeTarget);
    if (!Number.isFinite(target)) return;
    const row = $(`#studyList .study-row[data-offset="${target}"]`)
      || $('#studyList .study-row');
    if (!row) return;
""",
"""  function scrollToResumeWord() {
    const s = state.study;
    if (!s) return;
    const target = Number(s.resumeTarget);
    if (!Number.isFinite(target)) return;
    const first = s.items && s.items[0];
    if (first && Number(first.offset) === target && window.scrollY < 8) {
      s.pinActiveOffset = target;
      s.pinScrollY = window.scrollY;
      s.lastScrollY = window.scrollY;
      setActiveStudyRow(target);
      writeLocalStudyCursor(s.wordbookId, target);
      return;
    }
    const row = $(`#studyList .study-row[data-offset="${target}"]`)
      || $('#studyList .study-row');
    if (!row) return;
""",
"scrollToResumeWord skip jump")

repl(
"""    $('#exitStudy').onclick = () => { exitStudy(); };

    bindStudyStarButtons(root);
    (s.items || []).slice(0, 2).forEach((it) => { if (it?.word) prefetchSpeak(it.word); });
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
    if (jumpTo != null) {
      s.resumeTarget = jumpTo;
      setActiveStudyRow(jumpTo);
    }

    requestAnimationFrame(() => {
      scrollToResumeWord();
""",
"""    $('#exitStudy').onclick = () => { exitStudy(); };
    $('.study-top')?.classList.remove('is-away');

    bindStudyStarButtons(root);
    (s.items || []).slice(0, 2).forEach((it) => { if (it?.word) prefetchSpeak(it.word); });
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
    if (jumpTo != null) {
      s.resumeTarget = jumpTo;
      setActiveStudyRow(jumpTo);
    }

    requestAnimationFrame(() => {
      scrollToResumeWord();
""",
"renderStudy no is-away")

repl(
"""  function reviewDueCard(know) {
    const card = (state.due || [])[0];
    if (!card || state.reviewBusy) return;
    state.reviewBusy = true;
    state.due = (state.due || []).slice(1);
    paintDueCardFast();
    setTimeout(() => { state.reviewBusy = false; }, 180);
    api('/api/review', {
      method: 'POST',
      body: { vocab_id: card.id, rating: know ? 4 : 1 },
    }).catch((e) => {
      state.due = [card, ...(state.due || [])];
      if (state.tab === 'vocab' && !state.study) paintDueCardFast();
      toast(e.message);
    });
""",
"""  function reviewDueCard(know) {
    const card = (state.due || [])[0];
    const vocabId = Number(card?.id);
    if (!card || state.reviewBusy) return;
    if (!Number.isFinite(vocabId) || vocabId <= 0) return;
    state.reviewBusy = true;
    state.due = (state.due || []).slice(1);
    paintDueCardFast();
    setTimeout(() => { state.reviewBusy = false; }, 180);
    api('/api/review', {
      method: 'POST',
      body: { vocab_id: vocabId, rating: know ? 4 : 1 },
    }).catch((e) => {
      state.due = [card, ...(state.due || [])];
      if (state.tab === 'vocab' && !state.study) paintDueCardFast();
      const msg = String(e?.message || '').trim();
      if (msg && msg !== '\u8bf7\u6c42\u5931\u8d25') toast(msg);
    });
""",
"reviewDueCard toast + vocab_id")

p.write_text(js, encoding="utf-8")
print("wrote second batch, replacements", n)
