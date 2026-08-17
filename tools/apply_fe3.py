from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")

def once(text, old, new, label):
    if old not in text:
        raise SystemExit("MISSING " + label + "\n" + repr(old[:200]))
    return text.replace(old, new, 1)

t = once(t, """        const y = window.scrollY;
        if (y + 8 < (s.lastScrollY || 0)) {
          if (!s.allowLoadBefore) {
            s.allowLoadBefore = true;
            updateStudySentinels();
            watch($('#studySentinelTop'), 'before');
          }
        }
        s.lastScrollY = y;""", """        const y = window.scrollY;
        const topEl = $('.study-top');
        if (topEl) {
          if (y < 20) topEl.classList.remove('is-away');
          else if (y + 6 < (s.lastScrollY || 0)) topEl.classList.remove('is-away');
          else if (y > (s.lastScrollY || 0) + 6) topEl.classList.add('is-away');
        }
        if (y + 8 < (s.lastScrollY || 0)) {
          if (!s.allowLoadBefore) {
            s.allowLoadBefore = true;
            updateStudySentinels();
            watch($('#studySentinelTop'), 'before');
          }
        }
        s.lastScrollY = y;""", "scroll hide")

t = once(t, """    $('#exitStudy').onclick = async () => {
      await saveStudyCursor(true);
      patchBookProgressFromStudy();
      writeLastStudyBook(state.study?.wordbookId);
      if (state.study?.wordbookId != null && state.study.lastSavedCursor != null) {
        writeLocalStudyCursor(state.study.wordbookId, state.study.lastSavedCursor);
      }
      teardownStudyObservers();
      state.study = null;
      // Instant back — do not await full /api/wordbooks (was the slow return).
      renderBooks();
      loadBooks().catch(() => {});
    };""", """    $('#exitStudy').onclick = () => { exitStudy(); };""", "exit bind")

t = once(t, """  async function loadVocab() {
    const [vocab, due] = await Promise.all([
      api('/api/vocab'),
      api('/api/recommendations'),
    ]);
    state.vocab = vocab;
    state.due = due;
  }""", """  async function loadVocab() {
    state.due = await api('/api/recommendations');
  }""", "loadVocab")

p.write_text(t, encoding="utf-8")
print("scroll/exit/loadVocab ok")
