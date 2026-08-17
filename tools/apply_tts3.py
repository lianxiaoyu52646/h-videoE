from pathlib import Path

INSTANT = r'''function speakWord(word) {
  const w = String(word || '').trim();
  if (!w) return;
  try {
    if (window.speechSynthesis) {
      window.speechSynthesis.getVoices();
    }
  } catch (_) {}
  try {
    const bridge = window.AndroidDictionary;
    if (bridge && typeof bridge.speak === 'function') bridge.speak(w);
  } catch (_) {}
  try {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(w);
    u.lang = 'en-US';
    u.rate = 1.08;
    const voices = window.speechSynthesis.getVoices() || [];
    const voice = voices.find((v) => /en-US/i.test(v.lang)) || voices.find((v) => /^en/i.test(v.lang));
    if (voice) u.voice = voice;
    window.speechSynthesis.speak(u);
  } catch (_) {}
  try {
    if (!window._wpSpeakAudio) window._wpSpeakAudio = new Audio();
    const audio = window._wpSpeakAudio;
    const src = '/api/tts?q=' + encodeURIComponent(w);
    audio.onerror = null;
    try { audio.pause(); } catch (_) {}
    audio.src = src;
    const play = audio.play();
    if (play && play.catch) {
      play.catch((err) => {
        if (err && err.name === 'AbortError') return;
      });
    }
  } catch (_) {}
}
'''

def replace_fn(path, start_marker="function speakWord(word) {"):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    start = t.find(start_marker)
    if start < 0:
        raise SystemExit(f"no speakWord in {path}")
    # find next top-level function after this one
    rest = t[start + len(start_marker):]
    # end at next \nfunction or \n  function
    import re
    m = re.search(r"\n(?:async )?function |\n  async function |\n  function ", rest)
    if not m:
        raise SystemExit(f"no end in {path}")
    end = start + len(start_marker) + m.start() + 1
    t = t[:start] + INSTANT + t[end:]
    p.write_text(t, encoding="utf-8")
    print("patched", path)

replace_fn(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
replace_fn(r"D:\lian\praPro\h-videoE\app\static\js\wordbook-detail.js")
replace_fn(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\ui.js")
