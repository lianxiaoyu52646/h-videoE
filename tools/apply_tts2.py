from pathlib import Path

js_path = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = js_path.read_text(encoding="utf-8")

old = """    try { btn.blur(); } catch (_) {}
    speakWord(word);
  }, true);
"""
new = """    try { btn.blur(); } catch (_) {}
    unlockTts();
    speakWord(word);
  }, true);
"""
if old not in js:
    raise SystemExit("click handler missing")
js = js.replace(old, new, 1)

# prefetch current due card
old = """    $('#openVocabBookBtn')?.addEventListener('click', () => openVocabBook());
    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
"""
new = """    $('#openVocabBookBtn')?.addEventListener('click', () => openVocabBook());
    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
    if (current?.word) prefetchSpeak(current.word);
"""
if old not in js:
    raise SystemExit("renderVocab bind missing")
js = js.replace(old, new, 1)

# prefetch study rows
old = """    bindStudyStarButtons(root);
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
"""
new = """    bindStudyStarButtons(root);
    (s.items || []).slice(0, 10).forEach((it) => { if (it?.word) prefetchSpeak(it.word); });
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
"""
if old not in js:
    raise SystemExit("renderStudy bind missing")
js = js.replace(old, new, 1)

# warmup voices on boot
old = """    fetchAppVersion().catch(() => {});
"""
new = """    unlockTts();
    fetchAppVersion().catch(() => {});
"""
if old not in js:
    raise SystemExit("boot warmup missing")
js = js.replace(old, new, 1)

js_path.write_text(js, encoding="utf-8")
print("prefetch/warmup ok")

# backend timeout
main = Path(r"D:\lian\praPro\h-videoE\app\main.py")
mt = main.read_text(encoding="utf-8")
if "urlopen(req, timeout=10, context=ctx)" not in mt:
    raise SystemExit("tts timeout missing")
main.write_text(mt.replace("urlopen(req, timeout=10, context=ctx)", "urlopen(req, timeout=2.5, context=ctx)", 1), encoding="utf-8")
print("backend timeout ok")

idx = Path(r"D:\lian\praPro\h-videoE\app\static\m\index.html")
it = idx.read_text(encoding="utf-8")
it2 = it.replace("v=20260817.2", "v=20260817.3").replace("v=20260817.1", "v=20260817.3")
idx.write_text(it2, encoding="utf-8")
print("cache", it2.count("20260817.3"))
