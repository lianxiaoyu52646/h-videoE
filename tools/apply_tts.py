from pathlib import Path
js_path = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = js_path.read_text(encoding="utf-8")
start = js.find("  function speakWord(word) {")
end = js.find("  function speakBtnHtml(")
if start < 0 or end < 0:
    raise SystemExit(f"markers {start} {end}")

new = r'''  const _ttsCache = new Map();
  let _ttsGen = 0;
  let _ttsWarm = false;

  function ttsKey(word) {
    return String(word || '').trim().toLowerCase();
  }

  function unlockTts() {
    if (_ttsWarm) return;
    _ttsWarm = true;
    try {
      if (window.speechSynthesis) {
        window.speechSynthesis.getVoices();
        const warm = new SpeechSynthesisUtterance(' ');
        warm.volume = 0;
        window.speechSynthesis.speak(warm);
        window.speechSynthesis.cancel();
      }
    } catch (_) {}
    try {
      if (!window._wpSpeakAudio) window._wpSpeakAudio = new Audio();
      window._wpSpeakAudio.preload = 'auto';
    } catch (_) {}
  }

  function pickEnVoice() {
    try {
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      return (
        voices.find((v) => /en-US/i.test(v.lang) && /google|natural|enhanced|premium/i.test(v.name || '')) ||
        voices.find((v) => /^en(-|_|$)/i.test(v.lang)) ||
        null
      );
    } catch (_) {
      return null;
    }
  }

  function speakLocalNow(word) {
    let started = false;
    try {
      const bridge = window.AndroidDictionary;
      if (bridge && typeof bridge.speak === 'function') {
        bridge.speak(word);
        started = true;
      }
    } catch (_) {}
    try {
      if (!window.speechSynthesis) return started;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(word);
      u.lang = 'en-US';
      u.rate = 1.08;
      u.pitch = 1;
      const voice = pickEnVoice();
      if (voice) u.voice = voice;
      window.speechSynthesis.speak(u);
      started = true;
    } catch (_) {}
    return started;
  }

  function playCachedAudio(url, gen) {
    try {
      if (!window._wpSpeakAudio) window._wpSpeakAudio = new Audio();
      const audio = window._wpSpeakAudio;
      audio.onerror = null;
      try { audio.pause(); } catch (_) {}
      audio.src = url;
      const play = audio.play();
      if (play && typeof play.catch === 'function') {
        play.catch((err) => {
          if (gen !== _ttsGen) return;
          if (err && err.name === 'AbortError') return;
        });
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  async function fetchTtsBlob(word) {
    const urls = [
      '/api/tts?q=' + encodeURIComponent(word),
      'https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent(word),
    ];
    for (const url of urls) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 2500);
        const resp = await fetch(url, { signal: ctrl.signal, cache: 'force-cache' });
        clearTimeout(timer);
        if (!resp.ok) continue;
        const blob = await resp.blob();
        if (!blob || blob.size < 64) continue;
        return URL.createObjectURL(blob);
      } catch (_) {}
    }
    return null;
  }

  function prefetchSpeak(word) {
    const key = ttsKey(word);
    if (!key) return null;
    const hit = _ttsCache.get(key);
    if (hit) return hit;
    const pending = fetchTtsBlob(word).then((url) => {
      if (url) _ttsCache.set(key, url);
      else _ttsCache.delete(key);
      return url;
    });
    _ttsCache.set(key, pending);
    return pending;
  }

  function speakWord(word) {
    const w = String(word || '').trim();
    if (!w) return;
    unlockTts();
    const gen = ++_ttsGen;
    const key = ttsKey(w);
    const cached = _ttsCache.get(key);

    if (typeof cached === 'string') {
      playCachedAudio(cached, gen);
      return;
    }

    // Instant: local engine first, never wait on the network.
    speakLocalNow(w);
    const pending = cached && typeof cached.then === 'function' ? cached : prefetchSpeak(w);
    const t0 = Date.now();
    Promise.resolve(pending).then((url) => {
      if (!url || gen !== _ttsGen) return;
      // If real audio lands quickly, switch to it (clearer than device TTS).
      if (Date.now() - t0 < 420) {
        try { window.speechSynthesis && window.speechSynthesis.cancel(); } catch (_) {}
        playCachedAudio(url, gen);
      }
    });
  }

  window.__wpSpeakFallback = function (word) {
    speakWord(String(word || '').trim());
  };

'''
js = js[:start] + new + js[end:]
js_path.write_text(js, encoding="utf-8")
print("app.js speak replaced", js_path.stat().st_size)
