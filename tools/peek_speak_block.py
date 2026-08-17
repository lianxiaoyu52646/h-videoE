from pathlib import Path

js_path = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
js = js_path.read_text(encoding="utf-8")
old = """  /** Word TTS: same-origin /api/tts first — never silent-return on Android bridge alone. */
  function speakWord(word) {
    const w = String(word || '').trim();
    if (!w) {
      toast('没有可朗读的单词');
      return;
    }
    // Guaranteed audible path for App WebView (old APK used to swallow speak() and return).
    speakViaServerTts(w);
  }

  window.__wpSpeakFallback = function (word) {
    speakViaServerTts(String(word || '').trim());
  };

  function speakViaServerTts(word) {
    const w = String(word || '').trim();
    if (!w) return;
    const sources = [
      '/api/tts?q=' + encodeURIComponent(w),
      'https://dict.youdao.com/dictvoice?type=2&audio=' + encodeURIComponent(w),
      'https://dict.youdao.com/dictvoice?type=1&audio=' + encodeURIComponent(w),
    ];
    try {
      if (!window._wpSpeakAudio) window._wpSpeakAudio = new Audio();
      const audio = window._wpSpeakAudio;
      try { audio.pause(); } catch (_) {}
      let i = 0;
      const tryNative = () => {
        try {
          const bridge = window.AndroidDictionary;
          if (bridge && typeof bridge.speak === 'function') bridge.speak(w);
        } catch (_) {}
      };
      const tryNext = () => {
        if (i >= sources.length) {
          // Last resort: system TTS on device.
          tryNative();
          return;
        }
        const src = sources[i++];
        audio.onerror = tryNext;
        audio.src = src;
        const play = audio.play();
        if (play && typeof play.catch === 'function') play.catch(tryNext);
      };
      tryNext();
    } catch (_) {
      try {
        const bridge = window.AndroidDictionary;
        if (bridge && typeof bridge.speak === 'function') bridge.speak(w);
      } catch (__) {}
    }
  }
"""
# The file may have a special dash character. Locate by function names instead.
start = js.find("  function speakWord(word) {")
end = js.find("  function speakBtnHtml(")
if start < 0 or end < 0:
    raise SystemExit(f"markers {start} {end}")
print("block", start, end, "len", end-start)
print(repr(js[start-120:start]))
