from pathlib import Path
import re

better = r'''function speakWord(word) {
  const w = String(word || '').trim();
  if (!w) return;
  try { window.speechSynthesis && window.speechSynthesis.getVoices(); } catch (_) {}
  try {
    const bridge = window.AndroidDictionary;
    if (bridge && typeof bridge.speak === 'function') bridge.speak(w);
  } catch (_) {}
  try {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(w);
      u.lang = 'en-US';
      u.rate = 1.08;
      const voices = window.speechSynthesis.getVoices() || [];
      const voice = voices.find((v) => /en-US/i.test(v.lang)) || voices.find((v) => /^en/i.test(v.lang));
      if (voice) u.voice = voice;
      window.speechSynthesis.speak(u);
    }
  } catch (_) {}
  try {
    if (!window._wpSpeakAudio) window._wpSpeakAudio = new Audio();
    const audio = window._wpSpeakAudio;
    audio.onerror = null;
    audio.onplaying = () => { try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {} };
    try { audio.pause(); } catch (_) {}
    audio.src = '/api/tts?q=' + encodeURIComponent(w);
    const play = audio.play();
    if (play && play.catch) play.catch((err) => { if (err && err.name === 'AbortError') return; });
  } catch (_) {}
}
'''

def replace_fn(path):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    start = t.find("function speakWord(word) {")
    if start < 0:
        raise SystemExit("missing " + path)
    rest = t[start + 10:]
    m = re.search(r"\n(?:async )?function |\n  async function |\n  function ", rest)
    if not m:
        raise SystemExit("end missing " + path)
    end = start + 10 + m.start() + 1
    p.write_text(t[:start] + better + t[end:], encoding="utf-8")
    print("ok", path, "next", t[end:end+40].strip()[:40])

replace_fn(r"D:\lian\praPro\h-videoE\app\static\js\vocab.js")
replace_fn(r"D:\lian\praPro\h-videoE\app\static\js\wordbook-detail.js")
replace_fn(r"D:\lian\praPro\h-videoE\android\app\src\main\assets\js\ui.js")
