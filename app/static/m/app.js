(() => {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const state = {
    tab: 'read',
    user: null,
    shell: null,
    readings: [],
    library: [],
    wordbooks: null,
    vocab: [],
    due: [],
    eyecare: localStorage.getItem('wp_eyecare') === '1',
    reader: null,
    study: null, // bidirectional study session
    pk: { room: null, ws: null, wordbookId: null, pollTimer: null, feedback: null },
    bookTranslate: {
      scan: null,
      progress: null,
      checkpoint: null,
      resumable: false,
      running: false,
      loading: false,
      pollTimer: null,
      localRunning: false,
      localAbort: false,
      engine: '',
      currentTitle: '',
      modelPercent: null,
      logs: [],
      emptyClaimStreak: 0,
      failStreak: 0,
      phase: 'idle',
    },
  };

  if (!window.novelTranslateCallbacks) window.novelTranslateCallbacks = new Map();
  let _novelCbSeq = 0;
  const NOVEL_LOG_MAX = 400;
  if (!state.bookTranslate.logs) state.bookTranslate.logs = [];

  function novelLog(level, event, detail) {
    const ts = new Date().toISOString().slice(11, 23);
    const d = detail == null ? '' : (typeof detail === 'string' ? detail : JSON.stringify(detail));
    const line = `[${ts}][${level}] ${event}${d ? ' ' + d : ''}`;
    const bt = state.bookTranslate;
    if (!bt.logs) bt.logs = [];
    bt.logs.push(line);
    if (bt.logs.length > NOVEL_LOG_MAX) bt.logs.splice(0, bt.logs.length - NOVEL_LOG_MAX);
    try {
      if (level === 'E') console.error('[NovelTranslate]', event, detail || '');
      else if (level === 'W') console.warn('[NovelTranslate]', event, detail || '');
      else console.log('[NovelTranslate]', event, detail || '');
    } catch (_) {}
    const box = document.getElementById('novelTranslateLog');
    if (box) {
      box.textContent = bt.logs.slice(-120).join('\n');
      box.scrollTop = box.scrollHeight;
    } else if (typeof updateBookTranslateUi === 'function') {
      try { updateBookTranslateUi(); } catch (_) {}
    }
    return line;
  }

  function copyNovelLogs() {
    const text = (state.bookTranslate.logs || []).join('\n');
    if (!text) {
      toast('暂无日志');
      return;
    }
    const done = () => toast('翻译日志已复制');
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => {
        window.prompt('复制日志', text);
      });
    } else {
      window.prompt('复制日志', text);
    }
  }

  function nativeBridge() {
    try { return window.AndroidDictionary || null; } catch (_) { return null; }
  }

  function setTranslatePhase(phase, message) {
    const bt = state.bookTranslate;
    bt.phase = phase || 'idle';
    if (message) {
      bt.progress = {
        ...(bt.progress || {}),
        message,
        current_title: bt.currentTitle || bt.progress?.current_title || '',
      };
    }
    updateBookTranslateUi();
  }

  function updateBookTranslateUi() {
    if (state.tab !== 'mine') return;
    const bt = state.bookTranslate;
    const scan = bt.scan || {};
    const pending = Number(scan.pending_books || 0);
    const doneBooks = Number(scan.done_books || 0);
    const totalBooks = Number(scan.total_books || 0);
    const running = !!(bt.running || bt.localRunning);
    const statusEl = document.getElementById('btStatusLine');
    const bar = document.getElementById('btProgressBar');
    const cur = document.getElementById('btCurrentLine');
    const doneEl = document.getElementById('btDoneBooks');
    const pendingEl = document.getElementById('btPendingBooks');
    const totalEl = document.getElementById('btTotalBooks');
    const cta = document.getElementById('startTranslateBtn');
    const logBox = document.getElementById('novelTranslateLog');
    const phaseEl = document.getElementById('btPhaseHint');

    let statusLine = totalBooks ? '点击继续翻译开始' : '点击下方扫描经典书架';
    if (bt.phase === 'downloading' || typeof bt.modelPercent === 'number') {
      statusLine = `正在下载小说翻译模型 ${bt.modelPercent ?? 0}%（约1GB，请保持网络）`;
    } else if (bt.phase === 'loading') {
      statusLine = bt.progress?.message || '正在加载本地翻译引擎…';
    } else if (bt.phase === 'stopping') {
      statusLine = '正在停止翻译…';
    } else if (running) {
      statusLine = bt.progress?.message || `正在逐段翻译 · 已完成 ${doneBooks} 本 / 共 ${totalBooks} 本`;
    } else if (pending) {
      statusLine = `待译 ${pending} 本 · 已完成 ${doneBooks} 本（整本译完才 +1）`;
    } else if (totalBooks) {
      statusLine = '全部书籍已翻译完成';
    }

    const percent = (typeof bt.modelPercent === 'number')
      ? bt.modelPercent
      : (totalBooks ? Math.round((doneBooks / totalBooks) * 100) : Math.max(0, Number(bt.progress?.percent || 0)));

    if (statusEl) statusEl.textContent = statusLine;
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    if (doneEl) doneEl.textContent = String(doneBooks);
    if (pendingEl) pendingEl.textContent = String(pending);
    if (totalEl) totalEl.textContent = String(totalBooks);
    if (phaseEl) {
      const eng = bt.engine === 'qwen_local' ? 'Qwen本地' : (bt.engine === 'mlkit_fallback' ? '兼容引擎' : (bt.engine || '未启动'));
      phaseEl.textContent = `阶段:${bt.phase || 'idle'} · 引擎:${eng}`;
    }
    if (cur) {
      const t = bt.currentTitle || bt.progress?.current_title || '';
      cur.style.display = t && running ? '' : 'none';
      cur.textContent = t ? `当前：${t}` : '';
    }
    if (cta) {
      if (running || bt.localRunning) {
        cta.disabled = false;
        cta.textContent = '停止翻译';
      } else if (bt.phase === 'downloading') {
        cta.disabled = true;
        cta.textContent = '下载模型中…';
      } else if (bt.loading) {
        cta.disabled = true;
        cta.textContent = '启动中…';
      } else {
        cta.disabled = !(pending || bt.resumable || totalBooks);
        cta.textContent = (pending || bt.resumable) ? '继续翻译' : '开始翻译';
      }
    }
    if (logBox) {
      logBox.textContent = (bt.logs || []).slice(-120).join('\n') || '点击继续翻译后这里输出详细日志…';
      logBox.scrollTop = logBox.scrollHeight;
    }
  }

  function novelBridgeCall(method, ...args) {
    return new Promise((resolve, reject) => {
      try {
        const bridge = window.AndroidDictionary;
        if (!bridge || typeof bridge[method] !== 'function') {
          reject(new Error('需要 Android App'));
          return;
        }
        const id = `n${Date.now()}_${++_novelCbSeq}`;
        window.novelTranslateCallbacks.set(id, (payload) => {
          // Keep callback for download progress until phase ready / error terminal
          if (method === 'downloadNovelModel') {
            resolve(payload);
            if (payload && (payload.phase === 'ready' || payload.ok === false && payload.phase !== 'download')) {
              window.novelTranslateCallbacks.delete(id);
            }
            return;
          }
          window.novelTranslateCallbacks.delete(id);
          resolve(payload);
        });
        bridge[method](...args, id);
      } catch (e) {
        reject(e);
      }
    });
  }

  function translateNovelParagraph(enText) {
    const bridge = nativeBridge();
    if (bridge && typeof bridge.translateNovel === 'function') {
      return novelBridgeCall('translateNovel', enText || '').then((r) => {
        if (!r || !r.ok || !r.zh) throw new Error(r?.error || '翻译失败');
        if (r.engine) state.bookTranslate.engine = r.engine;
        return String(r.zh || '').trim();
      });
    }
    state.bookTranslate.engine = 'mlkit_fallback';
    return mlkitTranslateText(enText);
  }

  function mlkitTranslateText(enText) {
    return new Promise((resolve, reject) => {
      try {
        const bridge = nativeBridge();
        if (!bridge || typeof bridge.translateText !== 'function') {
          reject(new Error('当前 App 不支持翻译，请更新 App'));
          return;
        }
        if (!window.translationCallbacks) window.translationCallbacks = new Map();
        const id = `m${Date.now()}_${++_novelCbSeq}`;
        const timer = setTimeout(() => {
          window.translationCallbacks.delete(id);
          reject(new Error('兼容引擎翻译超时'));
        }, 90000);
        window.translationCallbacks.set(id, (zh) => {
          clearTimeout(timer);
          window.translationCallbacks.delete(id);
          const text = String(zh || '').trim();
          if (!text) reject(new Error('兼容引擎返回空译文'));
          else resolve(text);
        });
        bridge.translateText(enText || '', id);
      } catch (e) {
        reject(e);
      }
    });
  }

  async function ensureNovelModelReady() {
    const bridge = nativeBridge();
    const bt = state.bookTranslate;
    if (!bridge) throw new Error('请在 Android App 内使用离线翻译');
    const ver = cachedAppVersion || (await fetchAppVersion().catch(() => null));
    const modelUrl = (ver && ver.android_novel_model_url) || '';
    const modelName = (ver && ver.android_novel_model_name) || 'qwen2.5-1.5b-instruct-q4_k_m.gguf';
    novelLog('I', 'model.ensure', {
      modelName,
      hasUrl: !!modelUrl,
      hasDownload: typeof bridge.downloadNovelModel === 'function',
      hasTranslateNovel: typeof bridge.translateNovel === 'function',
      hasTranslateText: typeof bridge.translateText === 'function',
      apk: nativeApkMeta(),
    });

    if (typeof bridge.isNovelModelFileReady === 'function' && bridge.isNovelModelFileReady(modelName)) {
      setTranslatePhase('loading', '模型已在本地，正在加载翻译引擎…');
      if (typeof bridge.getNovelEngineName === 'function') bt.engine = bridge.getNovelEngineName() || '';
      novelLog('I', 'model.file_ready', { engine: bt.engine });
      return { engine: bt.engine || 'ready' };
    }

    if (modelUrl && typeof bridge.downloadNovelModel === 'function') {
      bt.phase = 'downloading';
      bt.modelPercent = 0;
      setTranslatePhase('downloading', '正在下载小说翻译模型 0%（约1GB，请保持网络）');
      toast('正在下载小说翻译模型，请勿退出…');
      novelLog('I', 'model.download.start', { modelUrl: modelUrl.slice(0, 160) });
      return new Promise((resolve, reject) => {
        const id = `n${Date.now()}_${++_novelCbSeq}`;
        window.novelTranslateCallbacks.set(id, (payload) => {
          if (!payload) return;
          if (payload.phase === 'download' && typeof payload.percent === 'number') {
            bt.modelPercent = payload.percent;
            setTranslatePhase('downloading', `正在下载小说翻译模型 ${payload.percent}%（约1GB）`);
            if (payload.percent % 5 === 0) novelLog('I', 'model.download.progress', { percent: payload.percent });
            return;
          }
          window.novelTranslateCallbacks.delete(id);
          bt.modelPercent = null;
          if (payload.ok) {
            bt.engine = payload.engine || '';
            setTranslatePhase('loading', '模型下载完成，正在加载引擎…');
            novelLog('I', 'model.download.done', payload);
            resolve(payload);
            return;
          }
          if (typeof bridge.translateText === 'function') {
            bt.engine = 'mlkit_fallback';
            novelLog('W', 'model.download.fail_fallback', { error: payload.error, engine: bt.engine });
            toast('模型下载失败，先用兼容引擎继续翻译');
            resolve({ ok: true, engine: bt.engine });
            return;
          }
          novelLog('E', 'model.download.fail', payload);
          reject(new Error(payload.error || '模型下载失败'));
        });
        try {
          bridge.downloadNovelModel(modelUrl, modelName, id);
        } catch (e) {
          window.novelTranslateCallbacks.delete(id);
          reject(e);
        }
      });
    }

    if (typeof bridge.translateText === 'function') {
      bt.engine = 'mlkit_fallback';
      setTranslatePhase('loading', '当前 App 暂用兼容引擎翻译（更新 App 可启用 Qwen）');
      novelLog('W', 'model.use_mlkit_only', { reason: 'no downloadNovelModel' });
      toast('使用兼容翻译引擎继续');
      return { engine: bt.engine };
    }
    throw new Error('翻译引擎未就绪，请更新 App');
  }

  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove('show'), 1800);
  }

  async function api(url, options = {}) {
    const opts = {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData)
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...(options.headers || {}),
      },
    };
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      opts.body = JSON.stringify(opts.body);
    }
    const resp = await fetch(url, opts);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detail = data.detail;
      throw new Error(typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : '请求失败');
    }
    return data;
  }

  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /** Word TTS: same-origin /api/tts first — never silent-return on Android bridge alone. */
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

  function speakBtnHtml(word, extraClass = '', { as = 'button' } = {}) {
    const w = String(word || '').trim();
    if (!w) return '';
    const cls = extraClass ? `speak-btn ${extraClass}` : 'speak-btn';
    const label = `朗读 ${escapeHtml(w)}`;
    const attrs = `class="${cls}" data-speak-word="${escapeHtml(w)}" aria-label="${label}" title="朗读"`;
    // Use <span> inside clickable rows — nested <button> breaks layout in browsers.
    if (as === 'span') {
      return `<span ${attrs} role="button" tabindex="0">🔊</span>`;
    }
    return `<button type="button" ${attrs}>🔊</button>`;
  }

  const WEB_VER_KEY = 'wp_web_content_version';
  let cachedAppVersion = null;

  function localWebVersion() {
    try { return localStorage.getItem(WEB_VER_KEY) || ''; } catch (_) { return ''; }
  }

  function rememberWebVersion(ver) {
    try { if (ver) localStorage.setItem(WEB_VER_KEY, String(ver)); } catch (_) {}
  }

  function nativeApkMeta() {
    try {
      const bridge = nativeBridge();
      if (!bridge) {
        const ua = navigator.userAgent || '';
        const uaApp = /\bwv\b|; wv\)/i.test(ua);
        return { code: 0, name: '', isApp: uaApp };
      }
      let code = 0;
      let name = '';
      try {
        if (typeof bridge.getVersionCode === 'function') code = Number(bridge.getVersionCode()) || 0;
      } catch (_) {}
      try {
        if (typeof bridge.getVersionName === 'function') name = String(bridge.getVersionName() || '');
      } catch (_) {}
      return { code, name, isApp: true };
    } catch (_) {
      return { code: 0, name: '', isApp: false };
    }
  }

  async function fetchAppVersion() {
    cachedAppVersion = await api('/api/app-version');
    // First visit: baseline so we don't nag until the next deploy.
    if (!localWebVersion() && cachedAppVersion?.web_content_version) {
      rememberWebVersion(cachedAppVersion.web_content_version);
    }
    return cachedAppVersion;
  }

  function applyWebPatch() {
    const ver = cachedAppVersion?.web_content_version || '';
    rememberWebVersion(ver);
    toast('正在更新内容…');
    try {
      const bridge = window.AndroidDictionary;
      if (bridge && typeof bridge.clearCacheAndReload === 'function') {
        bridge.clearCacheAndReload();
        return;
      }
    } catch (_) {}
    const url = new URL(location.href);
    url.searchParams.set('_v', ver || String(Date.now()));
    location.replace(url.toString());
  }

  function applyApkPatch(url) {
    const u = String(url || '').trim();
    if (!u) {
      toast('暂无安装包地址，请联系开发者');
      return;
    }
    try {
      const bridge = window.AndroidDictionary;
      if (bridge && typeof bridge.installApkFromUrl === 'function') {
        toast('正在下载安装包…');
        bridge.installApkFromUrl(u);
        return;
      }
    } catch (_) {}
    // Browser / no bridge: open download link
    window.open(u, '_blank');
  }

  async function checkForUpdate({ silent = false } = {}) {
    try {
      if (!silent) toast('正在检测…');
      const remote = await fetchAppVersion();
      const localWeb = localWebVersion();
      const webNewer = !!remote.web_content_version && remote.web_content_version !== localWeb;
      const apk = nativeApkMeta();
      const apkNewer =
        apk.isApp &&
        Number(remote.android_version_code || 0) > Number(apk.code || 0) &&
        !!String(remote.android_apk_url || '').trim();

      if (!webNewer && !apkNewer) {
        if (!silent) toast('已是最新版本');
        if (state.tab === 'mine') renderMine();
        return { webNewer, apkNewer, remote };
      }

      const kind = apkNewer ? (webNewer ? '网页与安装包' : '安装包') : '网页内容';
      const notes = remote.notes ? `<p class="m-muted">${escapeHtml(remote.notes)}</p>` : '';
      showModal(`
        <h3>发现新版本</h3>
        <p>有新的${kind}可更新。</p>
        ${notes}
        <p class="m-muted" style="font-size:0.82rem;">网页 ${escapeHtml(localWeb || '—')} → ${escapeHtml(remote.web_content_version || '—')}${
          apk.isApp ? `<br/>App ${escapeHtml(apk.name || String(apk.code))} → ${escapeHtml(remote.android_version_name || '')}` : ''
        }</p>
        <div class="binary-actions" style="margin-top:14px;">
          <button class="m-btn m-btn-ghost" id="updLater" type="button">稍后再说</button>
          <button class="m-btn m-btn-primary" id="updNow" type="button">立即更新</button>
        </div>`);
      $('#updLater').onclick = () => closeModal();
      $('#updNow').onclick = () => {
        closeModal();
        if (apkNewer) applyApkPatch(remote.android_apk_url);
        else applyWebPatch();
      };
      return { webNewer, apkNewer, remote };
    } catch (e) {
      if (!silent) toast(e.message || '检测失败');
      return null;
    }
  }

  function linkifyWords(text) {
    return String(text || '').replace(/([A-Za-z][A-Za-z'-]*)/g, (m) => {
      const clean = m.replace(/[^A-Za-z']/g, '');
      if (!clean) return escapeHtml(m);
      return `<span class="clickable-word" data-word="${escapeHtml(clean.toLowerCase())}">${escapeHtml(m)}</span>`;
    });
  }

  function showModal(html) {
    const host = $('#modalHost');
    host.innerHTML = `<div class="m-modal-mask"><div class="m-modal">${html}</div></div>`;
    host.querySelector('.m-modal-mask').addEventListener('click', (e) => {
      if (e.target.classList.contains('m-modal-mask')) closeModal();
    });
  }
  function closeModal() { $('#modalHost').innerHTML = ''; }

  function applyEyecare() {
    document.body.classList.toggle('eyecare', !!state.eyecare);
    localStorage.setItem('wp_eyecare', state.eyecare ? '1' : '0');
  }

  function setTab(tab) {
    const prev = state.tab;
    // Leaving 词书 while studying: freeze at current word index (local + server).
    if (prev === 'books' && tab !== 'books' && state.study) {
      pauseStudySession();
    }
    state.tab = tab;
    $$('#tabNav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${tab}`));
    if (tab === 'read') renderRead();
    if (tab === 'books') {
      // Coming back: reopen at the exact last word index.
      resumeStudySessionIfNeeded().catch(() => renderBooks());
    }
    if (tab === 'vocab') {
      renderVocab();
      refreshVocab().catch(() => {});
    }
    if (tab === 'pk') renderPk();
    if (tab === 'mine') {
      renderMine();
      refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    } else {
      stopBookTranslatePoll();
    }
  }

  function lastStudyBookKey() {
    return 'wp_last_study_book';
  }

  function writeLastStudyBook(wordbookId) {
    try {
      if (wordbookId != null) localStorage.setItem(lastStudyBookKey(), String(wordbookId));
    } catch (_) {}
  }

  function readLastStudyBook() {
    try {
      const n = Number(localStorage.getItem(lastStudyBookKey()));
      return Number.isFinite(n) && n > 0 ? n : null;
    } catch (_) {
      return null;
    }
  }

  function pauseStudySession() {
    const s = state.study;
    if (!s) return;
    // Capture visible/pinned index immediately.
    let cursor = s.pinActiveOffset != null ? Number(s.pinActiveOffset) : visibleStudyCursor();
    if (!Number.isFinite(cursor)) cursor = Number(s.lastSavedCursor || 0);
    cursor = Math.max(0, Math.floor(cursor));
    s.lastSavedCursor = cursor;
    s.resumeTarget = cursor;
    s.localResumeOffset = cursor;
    s.pinActiveOffset = cursor;
    writeLocalStudyCursor(s.wordbookId, cursor);
    writeLastStudyBook(s.wordbookId);
    patchBookProgressFromStudy();
    teardownStudyObservers();
    // Persist in background — don't block tab switch.
    saveStudyCursor(true).catch(() => {});
  }

  async function resumeStudySessionIfNeeded() {
    // Switched away mid-study: keep session and jump back to the last word index.
    if (state.study && state.study.bootstrapped) {
      const s = state.study;
      const cursor = Math.max(
        0,
        Math.floor(
          Number(
            s.lastSavedCursor ??
            readLocalStudyCursor(s.wordbookId) ??
            s.resumeTarget ??
            0
          )
        )
      );
      s.resumeTarget = cursor;
      s.lastSavedCursor = cursor;
      s.localResumeOffset = cursor;
      s.allowLoadBefore = false;
      writeLocalStudyCursor(s.wordbookId, cursor);
      writeLastStudyBook(s.wordbookId);
      const inWindow = (s.items || []).some((it) => Number(it.offset) === cursor);
      if (!inWindow) {
        await loadStudyPage('resume');
        return;
      }
      renderBooks();
      return;
    }
    renderBooks();
  }

  async function ensureAuth() {
    try {
      state.shell = await api('/api/app-shell');
      window.__APP_SHELL__ = state.shell;
      $('#appTitle').textContent = (state.shell.app_name || 'WordPop').split(' ')[0];
      applyEyecare();
      if (state.shell.supports_login) {
        state.user = await api('/api/auth/me');
      } else {
        state.user = { display_name: '本地学员', email: 'local' };
      }
      $('#userBtn').textContent = state.user.username || state.user.display_name || '我的';
      return true;
    } catch (_) {
      if (state.shell?.supports_login) {
        location.href = `/login?next=${encodeURIComponent('/app')}`;
        return false;
      }
      return true;
    }
  }

  // ---------- Read (fixed Gutenberg shelf) ----------
  async function loadReadings() {
    const [library, readings] = await Promise.all([
      api('/api/readings/library/books'),
      api('/api/readings').catch(() => []),
    ]);
    state.library = library || [];
    state.readings = readings || [];
  }

  function renderRead() {
    const root = $('#view-read');
    if (state.reader) return renderReader(root);

    const books = state.library || [];
    root.innerHTML = `
      <div class="m-hero">
        <h1>经典书架</h1>
        <p>古腾堡英文名著 · 点词查义 · 不会进生词本</p>
      </div>
      <div class="m-card">
        <div class="m-muted">共 ${books.length} 本</div>
      </div>
      <div class="wb-list">
        ${books.length ? books.map((b, i) => {
          const cover = bookCoverMeta(i, b.title);
          const pct = Math.min(100, Number(b.reading_read_progress) || 0);
          const opened = !!b.reading_document_id;
          const cta = opened ? (pct > 0 ? '继续读' : '打开') : '开始读';
          return `
            <button class="wb-card" data-lib-key="${escapeHtml(b.key)}" type="button">
              <div class="wb-cover ${cover.cls}" aria-hidden="true">
                <span class="wb-cover-emoji">${cover.emoji}</span>
                <span class="wb-cover-letter">${escapeHtml(cover.short)}</span>
              </div>
              <div class="wb-body">
                <div class="wb-title">${escapeHtml(b.title)}</div>
                <div class="wb-meta">${escapeHtml(b.author || 'Unknown')}</div>
                <div class="wb-progress-row">
                  <div class="progress-bar-wrap wb-progress">
                    <div class="progress-bar" style="width:${pct}%"></div>
                  </div>
                  <span class="wb-count">${pct}%</span>
                </div>
              </div>
              <span class="wb-cta">${cta}</span>
            </button>`;
        }).join('') : '<div class="m-card"><p class="m-muted">书架加载中…</p></div>'}
      </div>`;
    $$('[data-lib-key]').forEach((btn) => {
      btn.addEventListener('click', () => openLibraryBook(btn.dataset.libKey));
    });
  }

  async function openLibraryBook(bookKey) {
    try {
      toast('打开中…');
      const data = await api(`/api/readings/library/books/${encodeURIComponent(bookKey)}/import`, {
        method: 'POST',
      });
      const docId = data.reading?.id;
      if (!docId) throw new Error('打开失败');
      await openReader(Number(docId));
      loadReadings().catch(() => {});
    } catch (e) { toast(e.message); }
  }

  async function openReader(docId) {
    try {
      const boot = await api(`/api/readings/${docId}/bootstrap?limit=80&include_annotations=false`);
      const chapters = boot.chapters || [];
      const chapterIndex = Number(boot.chapter_index || 0);
      const chapter = chapters[chapterIndex] || null;
      state.reader = {
        doc: boot.doc || { id: docId },
        chapters,
        chapterIndex,
        chapter,
        blocks: boot.blocks || [],
        chapterOffset: 0,
        hasMore: !!(boot.has_more_blocks ?? ((boot.blocks || []).length >= 80)),
        loadingMore: false,
        showToc: false,
        translatePoll: 0,
        progressTimer: null,
      };
      requestChapterTranslate(docId, chapterIndex, true);
      pollReaderTranslations(docId);
      renderRead();
      // Resume near last block inside chapter if possible
      const resumeBlock = Number(boot.doc?.last_block_index || 0);
      if (resumeBlock > 0) {
        setTimeout(() => scrollToBlockOrder(resumeBlock), 80);
      }
    } catch (e) { toast(e.message); }
  }

  function requestChapterTranslate(docId, chapterIndex, prefetch) {
    api(
      `/api/readings/${docId}/translate/chapter/${chapterIndex}?prefetch_next=${prefetch ? 'true' : 'false'}`,
      { method: 'POST' },
    ).catch(() => {});
  }

  function scheduleSaveProgress(blockIndex) {
    const r = state.reader;
    if (!r?.doc?.id) return;
    clearTimeout(r.progressTimer);
    r.progressTimer = setTimeout(() => {
      api(`/api/readings/${r.doc.id}/progress`, {
        method: 'PATCH',
        body: { block_index: Math.max(0, Number(blockIndex) || 0) },
      }).then((doc) => {
        if (state.reader?.doc?.id === doc.id) state.reader.doc = doc;
      }).catch(() => {});
    }, 600);
  }

  function scrollToBlockOrder(orderIndex) {
    const el = document.querySelector(`.reader-line[data-order="${orderIndex}"]`);
    if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  async function openChapter(chapterIndex, { saveProgress = true } = {}) {
    const r = state.reader;
    if (!r) return;
    const idx = Math.max(0, Number(chapterIndex) || 0);
    const chapter = (r.chapters || [])[idx];
    if (!chapter) return;
    try {
      toast('切换章节…');
      const page = await api(
        `/api/readings/${r.doc.id}/chapters/${idx}/blocks?offset=0&limit=80`,
      );
      r.chapterIndex = idx;
      r.chapter = page.chapter || chapter;
      r.blocks = page.items || [];
      r.chapterOffset = 0;
      r.hasMore = !!(page.has_more ?? ((page.items || []).length >= 80));
      r.showToc = false;
      r.loadingMore = false;
      requestChapterTranslate(r.doc.id, idx, true);
      pollReaderTranslations(r.doc.id);
      if (saveProgress) scheduleSaveProgress(r.chapter.start_block || 0);
      renderRead();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) { toast(e.message); }
  }

  async function pollReaderTranslations(docId) {
    const r = state.reader;
    if (!r || r.doc.id !== docId) return;
    const token = (r.translatePoll || 0) + 1;
    r.translatePoll = token;
    const chapterIndex = r.chapterIndex;
    for (let i = 0; i < 12; i++) {
      await new Promise((res) => setTimeout(res, 1200));
      if (!state.reader || state.reader.doc.id !== docId || state.reader.translatePoll !== token) return;
      if (state.reader.chapterIndex !== chapterIndex) return;
      try {
        const loaded = state.reader.blocks.length;
        if (!loaded) return;
        const page = await api(
          `/api/readings/${docId}/chapters/${chapterIndex}/blocks?offset=0&limit=${Math.max(loaded, 80)}`,
        );
        const items = page.items || [];
        let changed = false;
        let stillMissing = false;
        items.forEach((b, idx) => {
          const cur = state.reader.blocks[idx];
          if (!cur || cur.id !== b.id) return;
          const nextTr = b.translation || '';
          if ((cur.translation || '') !== nextTr) {
            cur.translation = b.translation;
            changed = true;
          }
          if (!(cur.translation || '').trim()) stillMissing = true;
        });
        if (changed && state.tab === 'read') renderRead();
        if (!stillMissing) return;
      } catch (_) {}
    }
  }

  async function loadMoreReaderBlocks() {
    const r = state.reader;
    if (!r || r.loadingMore || !r.hasMore) return;
    r.loadingMore = true;
    try {
      const offset = (r.blocks || []).length;
      const page = await api(
        `/api/readings/${r.doc.id}/chapters/${r.chapterIndex}/blocks?offset=${offset}&limit=80`,
      );
      const items = page.items || [];
      if (items.length) {
        r.blocks = r.blocks.concat(items);
        r.hasMore = !!(page.has_more ?? (items.length >= 80));
        // Prefetch translate for newly visible absolute range via chapter job
        requestChapterTranslate(r.doc.id, r.chapterIndex, true);
        if (state.tab === 'read') renderRead();
      } else {
        r.hasMore = false;
        // Auto advance hint: if more chapters exist, keep hasMore false; user uses TOC / next chapter
      }
    } catch (_) {
      r.hasMore = false;
    } finally {
      r.loadingMore = false;
    }
  }

  function renderTocDrawer() {
    const r = state.reader;
    if (!r?.showToc) return '';
    const chapters = r.chapters || [];
    return `
      <div class="toc-mask" id="tocMask"></div>
      <aside class="toc-drawer" id="tocDrawer" role="dialog" aria-label="目录">
        <div class="toc-head">
          <div>
            <h3>目录</h3>
            <p class="m-muted">共 ${chapters.length} 章 · 列表内滑动查看</p>
          </div>
          <button class="m-btn m-btn-ghost" id="tocClose" type="button">关闭</button>
        </div>
        <div class="toc-list" id="tocList">
          ${chapters.length ? chapters.map((c, i) => `
            <button class="toc-item ${i === r.chapterIndex ? 'active' : ''}" type="button" data-chapter="${i}" title="${escapeHtml(c.title || `第 ${i + 1} 章`)}">
              <span class="toc-idx">${i + 1}</span>
              <span class="toc-title">${escapeHtml(c.title || `第 ${i + 1} 章`)}</span>
            </button>`).join('') : '<p class="m-muted" style="padding:12px;">暂无章节</p>'}
        </div>
      </aside>`;
  }

  function renderReader(root) {
    const { doc, blocks, chapter, chapters, chapterIndex } = state.reader;
    const chapterTitle = chapter?.title || `第 ${(chapterIndex || 0) + 1} 章`;
    const hasNext = (chapterIndex || 0) + 1 < (chapters || []).length;
    const hasPrev = (chapterIndex || 0) > 0;
    root.innerHTML = `
      <div class="reader-topbar m-card">
        <button class="m-btn m-btn-ghost" id="backShelf" type="button">书架</button>
        <div class="reader-top-mid">
          <h2>${escapeHtml(doc.title || '阅读')}</h2>
          <div class="m-muted">${escapeHtml(chapterTitle)}</div>
        </div>
        <div class="reader-top-actions">
          <button class="m-btn m-btn-sky" id="openToc" type="button">目录</button>
        </div>
      </div>
      <div class="reader-shell" id="readerBody">
        ${(blocks || []).map((b) => `
          <div class="reader-line" data-order="${b.order_index}">
            <div class="reader-en">${linkifyWords(b.text)}</div>
            <div class="reader-zh">${escapeHtml(b.translation || '（翻译生成中…）')}</div>
          </div>`).join('') || '<p class="m-muted">本章暂无内容</p>'}
        <div class="study-sentinel" id="readerSentinel">
          ${state.reader.hasMore ? '下滑加载更多…' : (hasNext ? '本章结束 · 可进下一章' : '全书到底啦')}
        </div>
        <div class="reader-nav">
          <button class="m-btn m-btn-ghost" id="prevChapter" type="button" ${hasPrev ? '' : 'disabled'}>上一章</button>
          <button class="m-btn m-btn-primary" id="nextChapter" type="button" ${hasNext ? '' : 'disabled'}>下一章</button>
        </div>
      </div>
      ${renderTocDrawer()}`;
    $('#backShelf').onclick = () => {
      const first = state.reader?.blocks?.[0]?.order_index;
      if (first != null) scheduleSaveProgress(first);
      state.reader = null;
      renderRead();
    };
    $('#openToc').onclick = () => { state.reader.showToc = true; renderRead(); };
    $('#tocClose')?.addEventListener('click', () => { state.reader.showToc = false; renderRead(); });
    $('#tocMask')?.addEventListener('click', () => { state.reader.showToc = false; renderRead(); });
    $$('[data-chapter]').forEach((btn) => {
      btn.addEventListener('click', () => openChapter(Number(btn.dataset.chapter)));
    });
    // Keep current chapter visible inside the fixed-height scroll list
    requestAnimationFrame(() => {
      $('#tocList .toc-item.active')?.scrollIntoView({ block: 'center', behavior: 'auto' });
    });
    $('#prevChapter')?.addEventListener('click', () => {
      if (hasPrev) openChapter(chapterIndex - 1);
    });
    $('#nextChapter')?.addEventListener('click', () => {
      if (hasNext) openChapter(chapterIndex + 1);
    });
    $('#readerBody')?.addEventListener('click', onWordClick);
    // Track reading position from visible lines
    const lines = $$('.reader-line');
    if (lines.length) {
      const ioProg = new IntersectionObserver((entries) => {
        const visible = entries
          .filter((en) => en.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (!visible.length) return;
        const order = Number(visible[0].target.getAttribute('data-order'));
        if (!Number.isNaN(order)) scheduleSaveProgress(order);
      }, { rootMargin: '-20% 0px -55% 0px', threshold: 0.1 });
      lines.slice(0, 12).forEach((el) => ioProg.observe(el));
      // Also observe mid pages when scrolling more
      if (lines.length > 12) lines[Math.floor(lines.length / 2)] && ioProg.observe(lines[Math.floor(lines.length / 2)]);
      if (lines.length > 2) ioProg.observe(lines[lines.length - 1]);
    }
    const sentinel = $('#readerSentinel');
    if (sentinel && state.reader.hasMore) {
      const io = new IntersectionObserver((entries) => {
        if (entries.some((en) => en.isIntersecting)) {
          io.disconnect();
          loadMoreReaderBlocks();
        }
      }, { rootMargin: '160px' });
      io.observe(sentinel);
    }
  }

  async function onWordClick(e) {
    const span = e.target.closest('.clickable-word');
    if (!span) return;
    const word = span.dataset.word;
    try {
      const data = await api(`/api/word-lookup/${encodeURIComponent(word)}`);
      const meaning = data.translation || data.youdao_translation || data.definition || '暂无释义';
      const headWord = data.word || word;
      showModal(`
        <h3 class="m-word-head">
          <span>${escapeHtml(headWord)}</span>
          ${speakBtnHtml(headWord, 'speak-btn-inline')}
        </h3>
        <p class="m-muted">${escapeHtml(data.pronunciation || '')}</p>
        <p>${escapeHtml(meaning)}</p>
        <div class="binary-actions" style="margin-top:14px;">
          <button class="m-btn m-btn-mint" id="knowWord" type="button">会</button>
          <button class="m-btn m-btn-danger" id="unknowWord" type="button">不会</button>
        </div>
        <button class="m-btn m-btn-ghost m-btn-block" style="margin-top:8px;" id="closeWord" type="button">关闭</button>`);
      $('#closeWord').onclick = closeModal;
      $('#knowWord').onclick = () => { closeModal(); toast('继续读～'); };
      $('#unknowWord').onclick = async () => {
        const line = span.closest('.reader-line');
        try {
          await api('/api/vocab/save', {
            method: 'POST',
            body: {
              word: data.word || word,
              source_platform: 'reading',
              source_video_id: `reading-${state.reader.doc.id}`,
              source_title: state.reader.doc.title,
              sentence: line?.querySelector('.reader-en')?.textContent || '',
              sentence_translation: line?.querySelector('.reader-zh')?.textContent || '',
              translation: data.translation,
              definition: data.definition,
              pronunciation: data.pronunciation,
            },
          });
          closeModal();
          toast('已进生词本');
          await refreshVocab();
        } catch (err) {
          toast(err.message || '加入生词本失败');
        }
      };
    } catch (err) { toast(err.message); }
  }

  // ---------- Wordbooks (star + infinite scroll) ----------
  async function loadBooks() {
    try {
      let books = await api('/api/wordbooks');
      if (!Array.isArray(books)) books = [];
      if (!books.length) {
        const ensured = await api('/api/wordbooks/ensure', { method: 'POST' });
        books = Array.isArray(ensured?.books) ? ensured.books : await api('/api/wordbooks');
      }
      state.wordbooks = books;
    } catch (e) {
      state.wordbooks = [];
      toast(e.message || '词书加载失败');
      throw e;
    }
  }

  function bookCoverMeta(index, name) {
    const palettes = [
      { cls: 'cover-coral', emoji: '📚' },
      { cls: 'cover-aqua', emoji: '🚀' },
      { cls: 'cover-sky', emoji: '🌈' },
      { cls: 'cover-lemon', emoji: '⚡' },
      { cls: 'cover-peach', emoji: '🫧' },
    ];
    const p = palettes[index % palettes.length];
    const short = (name || '词').trim().slice(0, 1) || '词';
    return { ...p, short };
  }

  function renderBooks() {
    const root = $('#view-books');
    if (state.study) return renderStudy(root);

    const books = state.wordbooks;
    const loading = books == null;
    const list = books || [];
    root.innerHTML = `
      <div class="m-hero wb-hero">
        <h1>词书闯关</h1>
        <p>点星=不会 · 不点=会</p>
      </div>
      <div class="wb-list">
        ${loading ? '<div class="m-card"><p class="m-muted">词书加载中…</p></div>'
          : (list.length ? list.map((b, i) => {
          const cover = bookCoverMeta(i, b.name);
          const pct = Math.min(100, Number(b.study_percent) || 0);
          const label = b.study_label || `0 / ${b.entry_count || 0}`;
          const started = (Number(b.study_seen) || 0) > 0;
          const done = pct >= 100;
          const cta = done ? '再刷一遍' : (started ? '继续刷' : '开始闯关');
          return `
            <button class="wb-card" data-study="${b.id}" type="button">
              <div class="wb-cover ${cover.cls}" aria-hidden="true">
                <span class="wb-cover-emoji">${cover.emoji}</span>
                <span class="wb-cover-letter">${escapeHtml(cover.short)}</span>
              </div>
              <div class="wb-body">
                <div class="wb-title">${escapeHtml(b.name)}</div>
                <div class="wb-progress-row">
                  <div class="progress-bar-wrap wb-progress">
                    <div class="progress-bar" style="width:${pct}%"></div>
                  </div>
                  <span class="wb-count">${escapeHtml(label)}</span>
                </div>
              </div>
              <span class="wb-cta">${cta}</span>
            </button>`;
        }).join('') : `<div class="m-card">
            <p class="m-muted">暂无词书</p>
            <button class="m-btn m-btn-primary" type="button" id="retryBooksBtn">重新加载词书</button>
          </div>`)}
      </div>`;
    $$('[data-study]').forEach((btn) => {
      btn.addEventListener('click', () => startStudy(Number(btn.dataset.study)));
    });
    $('#retryBooksBtn')?.addEventListener('click', async () => {
      try {
        toast('正在加载词书…');
        await loadBooks();
        renderBooks();
        if (!(state.wordbooks || []).length) toast('仍无词书，请重新登录后再试');
      } catch (e) {
        toast(e.message || '词书加载失败');
      }
    });
  }

  async function startStudy(wordbookId) {
    teardownStudyObservers();
    const localCursor = readLocalStudyCursor(wordbookId);
    writeLastStudyBook(wordbookId);
    state.study = {
      wordbookId,
      name: '',
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
    await loadStudyPage('resume');
  }

  function studyCursorKey(wordbookId) {
    return `wp_study_cursor_${wordbookId}`;
  }

  function readLocalStudyCursor(wordbookId) {
    try {
      const raw = localStorage.getItem(studyCursorKey(wordbookId));
      if (raw == null || raw === '') return null;
      const n = Number(raw);
      return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
    } catch (_) {
      return null;
    }
  }

  function writeLocalStudyCursor(wordbookId, cursor) {
    try {
      localStorage.setItem(studyCursorKey(wordbookId), String(Math.max(0, Math.floor(Number(cursor) || 0))));
    } catch (_) {}
  }

  function patchBookProgressFromStudy() {
    const s = state.study;
    if (!s || !Array.isArray(state.wordbooks)) return;
    const book = state.wordbooks.find((b) => Number(b.id) === Number(s.wordbookId));
    if (!book) return;
    const total = s.total || book.entry_count || 0;
    const cursor = s.lastSavedCursor != null ? s.lastSavedCursor : (s.progress?.cursor || 0);
    const at = Math.min(total, Math.max(0, cursor) + 1);
    book.study_seen = Math.max(Number(book.study_seen) || 0, at);
    book.study_label = total ? `${at} / ${total}` : book.study_label;
    book.study_percent = total ? Math.min(100, Math.round((at / total) * 100)) : book.study_percent;
    book.study_cursor = cursor;
  }

  function teardownStudyObservers() {
    const s = state.study;
    if (!s) return;
    (s.observers || []).forEach((io) => io.disconnect());
    s.observers = [];
    if (s.onScroll) {
      window.removeEventListener('scroll', s.onScroll);
      s.onScroll = null;
    }
    if (s.cursorTimer) {
      clearTimeout(s.cursorTimer);
      s.cursorTimer = null;
    }
  }

  function syncStudyBounds() {
    const s = state.study;
    if (!s) return;
    const total = Number(s.total || 0);
    s.hasMoreBefore = s.startOffset > 0;
    s.hasMoreAfter = total > 0 ? s.nextOffset < total : false;
  }

  function studyRowHtml(it, { animate = false } = {}) {
    const s = state.study;
    const idx = it.index != null ? it.index : (Number(it.offset) + 1);
    return `
      <div class="study-row${animate ? ' is-new' : ''}" data-id="${it.id}" data-offset="${it.offset ?? ''}">
        <div class="study-row-main">
          <div class="study-row-idx">#${idx}</div>
          <div class="en">${escapeHtml(it.word)}</div>
          ${it.pronunciation ? `<div class="phon">${escapeHtml(it.pronunciation)}</div>` : ''}
          <div class="zh">${escapeHtml(it.translation || '')}</div>
        </div>
        <div class="study-row-actions">
          ${speakBtnHtml(it.word)}
          <button class="star-btn ${s.starred.has(it.id) ? 'on' : ''}" data-star="${it.id}" type="button" aria-label="不会">
            ${s.starred.has(it.id) ? '★' : '☆'}
          </button>
        </div>
      </div>`;
  }

  function setActiveStudyRow(offset) {
    const s = state.study;
    if (!s) return;
    const off = Number(offset);
    if (!Number.isFinite(off)) return;
    if (s.activeOffset === off) {
      const current = $(`#studyList .study-row.is-active`);
      if (current && Number(current.dataset.offset) === off) return;
    }
    s.activeOffset = off;
    $$('#studyList .study-row.is-active').forEach((el) => el.classList.remove('is-active'));
    const row = $(`#studyList .study-row[data-offset="${off}"]`);
    if (row) row.classList.add('is-active');
  }

  function syncActiveStudyRowFromScroll() {
    const s = state.study;
    if (!s) return;
    // Click-selected row stays until the user actually scrolls away.
    if (s.pinActiveOffset != null) {
      const moved = Math.abs(window.scrollY - (s.pinScrollY ?? window.scrollY));
      if (moved < 48) {
        setActiveStudyRow(s.pinActiveOffset);
        return;
      }
      s.pinActiveOffset = null;
      s.pinScrollY = null;
    }
    setActiveStudyRow(visibleStudyCursor());
  }

  function bindStudyRowSelection(scope) {
    const s = state.study;
    if (!s) return;
    const root = scope || document;
    $$('.study-row[data-offset]', root).forEach((row) => {
      if (row.dataset.selectBound === '1') return;
      row.dataset.selectBound = '1';
      row.addEventListener('click', (e) => {
        if (e.target.closest('.speak-btn, .star-btn, [data-speak-word], [data-star]')) return;
        const off = Number(row.dataset.offset);
        if (!Number.isFinite(off)) return;
        // Select in place — do not scroll (was jumping to the next word).
        s.pinActiveOffset = off;
        s.pinScrollY = window.scrollY;
        setActiveStudyRow(off);
        s.lastSavedCursor = off;
        updateStudyProgressUi();
        scheduleSaveStudyCursor();
      });
    });
  }

  function bindStudyStarButtons(scope) {
    const s = state.study;
    if (!s) return;
    bindStudyRowSelection(scope);
    $$('[data-star]', scope || document).forEach((btn) => {
      if (btn.dataset.bound === '1') return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', async () => {
        const id = Number(btn.dataset.star);
        const on = !s.starred.has(id);
        if (on) s.starred.add(id);
        else s.starred.delete(id);
        btn.classList.toggle('on', on);
        btn.textContent = on ? '★' : '☆';
        btn.classList.add('pop');
        setTimeout(() => btn.classList.remove('pop'), 280);
        try {
          const res = await api(`/api/wordbooks/${s.wordbookId}/study-star`, {
            method: 'POST',
            body: { entry_id: id, starred: on },
          });
          if (res.progress) {
            s.progress = res.progress;
            updateStudyProgressUi();
          }
          toast(on ? '已进生词本' : '已取消');
          refreshVocab().catch(() => {});
        } catch (e) { toast(e.message); }
      });
    });
  }

  function updateStudyProgressUi() {
    const s = state.study;
    if (!s?.progress) return;
    const meta = $('.study-top-meta');
    const bar = $('.study-top .progress-bar');
    const pct = Math.min(100, Number(s.progress.percent) || 0);
    const total = s.total || s.progress.total || 0;
    const cursor = s.lastSavedCursor != null ? s.lastSavedCursor : (s.progress.cursor || 0);
    const label = total ? `${cursor + 1} / ${total}` : (s.progress.label || '0 / 0');
    if (meta) meta.textContent = `${label} · ${pct}%`;
    if (bar) bar.style.width = `${pct}%`;
  }

  function updateStudySentinels() {
    const s = state.study;
    if (!s) return;
    syncStudyBounds();
    const top = $('#studySentinelTop');
    const bottom = $('#studySentinelBottom');
    if (top) {
      top.textContent = s.loadingBefore
        ? '加载前面的单词…'
        : (s.hasMoreBefore
          ? (s.allowLoadBefore ? '↑ 继续上滑 · 回到更早的词' : '↑ 上滑可查看更早的词')
          : '▲ 词书开头（第 1 个词）');
    }
    if (bottom) {
      const total = s.total || 0;
      bottom.textContent = s.loadingAfter
        ? '加载后面的单词…'
        : (s.hasMoreAfter
          ? '↓ 继续下滑 · 查看更多'
          : (total ? `▼ 词书末尾（第 ${total} 个词）` : '▼ 词书末尾'));
    }
  }

  function appendStudyRows(items) {
    const list = $('#studyList');
    if (!list || !items.length) return;
    const wrap = document.createElement('div');
    wrap.innerHTML = items.map((it) => studyRowHtml(it, { animate: false })).join('');
    [...wrap.children].forEach((n) => list.appendChild(n));
    bindStudyStarButtons(list);
    if (state.study?.activeOffset != null) setActiveStudyRow(state.study.activeOffset);
  }

  function prependStudyRows(items) {
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
  }

  /** Keep DOM small: only ~WINDOW rows stay mounted while scrolling a large book. */
  const STUDY_DOM_WINDOW = 72;

  function trimStudyDom(direction) {
    const s = state.study;
    const list = $('#studyList');
    if (!s || !list || s.items.length <= STUDY_DOM_WINDOW) return;

    const drop = s.items.length - STUDY_DOM_WINDOW;
    if (drop <= 0) return;

    if (direction === 'after') {
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
    }
    syncStudyBounds();
    updateStudySentinels();
  }

  function applyStudyPage(data, mode) {
    const s = state.study;
    if (!s) return [];
    const items = data.items || [];
    const pageOffset = Number(data.offset ?? 0);
    const pageLimit = Math.max(1, Number(data.limit ?? 30));
    s.total = Number(data.total ?? s.total ?? 0);
    s.name = data.name || s.name;
    s.progress = data.progress || s.progress;

    if (mode === 'resume') {
      s.items = items;
      s.starred = new Set(items.filter((it) => it.starred).map((it) => it.id));
      s.startOffset = pageOffset;
      s.nextOffset = pageOffset + items.length;
      s.resumeTarget = Number(
        data.resume_offset ?? data.progress?.cursor ?? pageOffset
      );
      if (s.total) {
        s.resumeTarget = Math.max(0, Math.min(s.resumeTarget, s.total - 1));
      }
      s.lastSavedCursor = s.resumeTarget;
      syncStudyBounds();
      return items;
    }

    if (mode === 'after') {
      if (pageOffset < s.nextOffset) {
        const allDup = items.length > 0 && items.every((it) => s.items.some((x) => x.id === it.id));
        if (allDup) {
          s.nextOffset = Math.max(s.nextOffset, pageOffset + Math.max(items.length, pageLimit));
          syncStudyBounds();
          return [];
        }
      }
      const seen = new Set(s.items.map((it) => it.id));
      const fresh = items.filter((it) => !seen.has(it.id));
      fresh.forEach((it) => { if (it.starred) s.starred.add(it.id); });
      if (fresh.length) s.items = s.items.concat(fresh);
      s.nextOffset = Math.max(
        s.nextOffset,
        pageOffset + (items.length || pageLimit),
        fresh.length ? Number(fresh[fresh.length - 1].offset) + 1 : 0,
      );
      syncStudyBounds();
      return fresh;
    }

    if (mode === 'before') {
      const seen = new Set(s.items.map((it) => it.id));
      const fresh = items.filter((it) => !seen.has(it.id));
      fresh.forEach((it) => { if (it.starred) s.starred.add(it.id); });
      if (fresh.length) {
        s.items = fresh.concat(s.items);
        s.startOffset = Number(fresh[0].offset ?? pageOffset);
      } else {
        s.startOffset = Math.min(s.startOffset, pageOffset);
      }
      syncStudyBounds();
      return fresh;
    }
    return [];
  }

  async function loadStudyPage(mode) {
    const s = state.study;
    if (!s) return;
    if (mode === 'before') {
      if (!s.allowLoadBefore || s.loadingBefore || !s.hasMoreBefore) return;
      s.loadingBefore = true;
    } else if (mode === 'after') {
      if (s.loadingAfter || !s.hasMoreAfter) return;
      s.loadingAfter = true;
    } else if (s.loadingAfter || s.loadingBefore) {
      return;
    } else {
      s.loadingAfter = true;
    }

    const seq = (s.feedSeq = (s.feedSeq || 0) + 1);
    const pageSize = 36;
    updateStudySentinels();

    try {
      let url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}`;
      if (mode === 'after') {
        // Use prefetched page if available.
        if (s.prefetchAfter && Number(s.prefetchAfter.offset) === Number(s.nextOffset)) {
          const data = s.prefetchAfter;
          s.prefetchAfter = null;
          if (state.study !== s || seq !== s.feedSeq) return;
          const fresh = applyStudyPage(data, 'after');
          appendStudyRows(fresh);
          trimStudyDom('after');
          updateStudyProgressUi();
          updateStudySentinels();
          schedulePrefetchAfter();
          return;
        }
        url += `&offset=${s.nextOffset}`;
      } else if (mode === 'before') {
        const limit = Math.min(pageSize, s.startOffset);
        const offset = Math.max(0, s.startOffset - limit);
        url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${limit}&offset=${offset}`;
      } else if (mode === 'resume') {
        const local = s.localResumeOffset;
        if (local != null && Number.isFinite(local) && local >= 0) {
          url += `&offset=${Math.floor(local)}`;
        }
      }
      let data = await api(url);
      if (state.study !== s || seq !== s.feedSeq) return;

      let resumeKeep = null;
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
            `/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}&offset=${target}`
          );
          if (state.study !== s || seq !== s.feedSeq) return;
        }
        resumeKeep = target;
        writeLocalStudyCursor(s.wordbookId, target);
      }

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
        renderBooks();
        schedulePrefetchAfter();
        return;
      }

      if (mode === 'after') {
        appendStudyRows(fresh);
        trimStudyDom('after');
        schedulePrefetchAfter();
      } else if (mode === 'before') {
        prependStudyRows(fresh);
        trimStudyDom('before');
      }
      updateStudyProgressUi();
      updateStudySentinels();
    } catch (e) {
      toast(e.message);
    } finally {
      if (state.study === s) {
        if (mode === 'before') s.loadingBefore = false;
        else s.loadingAfter = false;
        updateStudySentinels();
      }
    }
  }

  function schedulePrefetchAfter() {
    const s = state.study;
    if (!s || !s.hasMoreAfter || s.prefetching || s.loadingAfter) return;
    const next = s.nextOffset;
    if (s.prefetchAfter && Number(s.prefetchAfter.offset) === Number(next)) return;
    s.prefetching = true;
    const pageSize = 36;
    api(`/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}&offset=${next}`)
      .then((data) => {
        if (state.study !== s) return;
        if (Number(data.offset) === Number(s.nextOffset)) s.prefetchAfter = data;
      })
      .catch(() => {})
      .finally(() => {
        if (state.study === s) s.prefetching = false;
      });
  }

  function visibleStudyCursor() {
    const s = state.study;
    if (!s || !s.items.length) return 0;
    const rows = $$('#studyList .study-row[data-offset]');
    const topPad = 100;
    for (const row of rows) {
      const rect = row.getBoundingClientRect();
      if (rect.bottom > topPad) return Number(row.dataset.offset);
    }
    return Number(s.items[s.items.length - 1].offset || 0);
  }

  async function saveStudyCursor(force = false) {
    const s = state.study;
    if (!s) return;
    let cursor;
    if (s.pinActiveOffset != null) {
      cursor = Number(s.pinActiveOffset);
      setActiveStudyRow(cursor);
    } else {
      cursor = visibleStudyCursor();
      setActiveStudyRow(cursor);
    }
    if (!Number.isFinite(cursor)) return;
    cursor = Math.max(0, Math.floor(cursor));
    writeLocalStudyCursor(s.wordbookId, cursor);
    if (!force && s.lastSavedCursor === cursor) return;
    s.lastSavedCursor = cursor;
    updateStudyProgressUi();
    try {
      const res = await api(`/api/wordbooks/${s.wordbookId}/study-cursor`, {
        method: 'POST',
        body: { cursor },
      });
      if (res.progress) {
        s.progress = res.progress;
        updateStudyProgressUi();
      }
    } catch (_) {}
  }

  function scheduleSaveStudyCursor() {
    const s = state.study;
    if (!s) return;
    clearTimeout(s.cursorTimer);
    // Local index is instant; avoid Neon writes while finger is scrolling.
    const cursor = s.pinActiveOffset != null ? Number(s.pinActiveOffset) : visibleStudyCursor();
    if (Number.isFinite(cursor)) {
      writeLocalStudyCursor(s.wordbookId, cursor);
      s.lastSavedCursor = Math.floor(cursor);
      s.serverCursorDirty = true;
      updateStudyProgressUi();
    }
    s.cursorTimer = setTimeout(() => {
      if (!s.serverCursorDirty) return;
      s.serverCursorDirty = false;
      saveStudyCursor(true);
    }, 2500);
  }

  function attachStudyObservers() {
    const s = state.study;
    if (!s) return;
    (s.observers || []).forEach((io) => io.disconnect());
    s.observers = [];
    if (s.onScroll) {
      window.removeEventListener('scroll', s.onScroll);
      s.onScroll = null;
    }
    syncStudyBounds();

    const watch = (el, mode) => {
      if (!el) return;
      if (mode === 'before' && !s.allowLoadBefore) return;
      const io = new IntersectionObserver((entries) => {
        if (!entries.some((en) => en.isIntersecting)) return;
        loadStudyPage(mode);
      }, { rootMargin: mode === 'after' ? '280px' : '40px', threshold: 0 });
      io.observe(el);
      s.observers.push(io);
    };

    if (s.hasMoreBefore && s.allowLoadBefore) watch($('#studySentinelTop'), 'before');
    if (s.hasMoreAfter) watch($('#studySentinelBottom'), 'after');

    s.lastScrollY = window.scrollY;
    let scrollRaf = 0;
    s.onScroll = () => {
      if (scrollRaf) return;
      scrollRaf = requestAnimationFrame(() => {
        scrollRaf = 0;
        const y = window.scrollY;
        if (y + 8 < (s.lastScrollY || 0)) {
          if (!s.allowLoadBefore) {
            s.allowLoadBefore = true;
            updateStudySentinels();
            watch($('#studySentinelTop'), 'before');
          }
        }
        s.lastScrollY = y;
        syncActiveStudyRowFromScroll();
        scheduleSaveStudyCursor();
        // Warm next page early while user is still reading.
        if (s.hasMoreAfter && !s.prefetchAfter && !s.prefetching) schedulePrefetchAfter();
      });
    };
    window.addEventListener('scroll', s.onScroll, { passive: true });
    syncActiveStudyRowFromScroll();
    schedulePrefetchAfter();
  }

  function scrollToResumeWord() {
    const s = state.study;
    if (!s) return;
    const target = Number(s.resumeTarget);
    if (!Number.isFinite(target)) return;
    const row = $(`#studyList .study-row[data-offset="${target}"]`)
      || $('#studyList .study-row');
    if (!row) return;
    // Jump without smooth scroll — precise and fast on mobile WebView.
    const y = row.getBoundingClientRect().top + window.scrollY - 88;
    window.scrollTo(0, Math.max(0, y));
    s.pinActiveOffset = Number(row.dataset.offset ?? target);
    s.pinScrollY = window.scrollY;
    s.lastScrollY = window.scrollY;
    setActiveStudyRow(s.pinActiveOffset);
    writeLocalStudyCursor(s.wordbookId, s.pinActiveOffset);
  }

  function renderStudy(root) {
    const s = state.study;
    teardownStudyObservers();
    syncStudyBounds();
    const p = s.progress || { label: '0 / 0', percent: 0 };
    const pct = Math.min(100, Number(p.percent) || 0);
    const total = s.total || p.total || 0;
    const at = (s.resumeTarget || 0) + 1;
    root.innerHTML = `
      <div class="study-top">
        <button class="study-back" id="exitStudy" type="button" aria-label="返回">←</button>
        <div class="study-top-main">
          <div class="study-top-title">${escapeHtml(s.name || '词书')}</div>
          <div class="study-top-meta">${total ? `${at} / ${total}` : escapeHtml(p.label || '0 / 0')} · ${pct}%</div>
          <div class="progress-bar-wrap"><div class="progress-bar" style="width:${pct}%"></div></div>
        </div>
      </div>
      <div class="study-sentinel study-sentinel-top" id="studySentinelTop">${
        s.hasMoreBefore
          ? (s.allowLoadBefore ? '↑ 继续上滑 · 回到更早的词' : '↑ 上滑可查看更早的词')
          : '▲ 词书开头（第 1 个词）'
      }</div>
      <div id="studyList" class="study-list">
        ${s.items.map((it) => studyRowHtml(it)).join('')}
      </div>
      <div class="study-sentinel" id="studySentinelBottom">${
        s.hasMoreAfter
          ? '↓ 继续下滑 · 查看更多'
          : (total ? `▼ 词书末尾（第 ${total} 个词）` : '▼ 词书末尾')
      }</div>`;

    $('#exitStudy').onclick = async () => {
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
    };

    bindStudyStarButtons(root);
    const jumpTo = s.lastSavedCursor != null ? s.lastSavedCursor : s.resumeTarget;
    if (jumpTo != null) {
      s.resumeTarget = jumpTo;
      setActiveStudyRow(jumpTo);
    }

    requestAnimationFrame(() => {
      scrollToResumeWord();
      // Second frame: settle after layout, then enable downward infinite scroll only.
      requestAnimationFrame(() => {
        if (state.study === s) attachStudyObservers();
      });
    });
  }

  // ---------- Vocab + Daily FSRS ----------
  async function loadVocab() {
    const [vocab, due] = await Promise.all([
      api('/api/vocab'),
      api('/api/recommendations'),
    ]);
    state.vocab = vocab;
    state.due = due;
  }

  /** Reload vocab cache; re-render if user is on the 生词 tab. */
  async function refreshVocab() {
    await loadVocab();
    if (state.tab === 'vocab') renderVocab();
  }

  function renderVocab() {
    const root = $('#view-vocab');
    const due = state.due || [];
    const current = due[0];
    const warehouse = state.vocab || [];
    root.innerHTML = `
      <div class="m-hero">
        <h1>生词 · 记忆</h1>
        <p>到期词逐个练习；生词本可随时移出。</p>
      </div>
      <div class="m-card">
        <h2>今日练习 · 到期 ${due.length} 个</h2>
        <p class="m-muted" style="margin:0 0 12px;">「会」延后复习，「不会」尽快再练。练习不会删词。</p>
        ${current ? `
          <div class="flash-card">
            <div class="flash-word-row">
              <div class="flash-word">${escapeHtml(current.word)}</div>
              ${speakBtnHtml(current.word, 'speak-btn-lg')}
            </div>
            <div class="flash-phonetic">${escapeHtml(current.pronunciation || '')}</div>
            <div class="flash-meaning">${escapeHtml(current.translation || current.definition || '')}</div>
          </div>
          <div class="binary-actions">
            <button class="m-btn m-btn-mint" id="reviewKnow" type="button">会</button>
            <button class="m-btn m-btn-danger" id="reviewUnknown" type="button">不会</button>
          </div>
        ` : '<p class="m-muted">暂无到期词。去阅读 / 词书 / 对战收藏生词后，到期会自动出现在这里。</p>'}
      </div>
      <div class="m-card">
        <h2>生词本 · 全部 (${warehouse.length})</h2>
        <p class="m-muted" style="margin:0 0 10px;">点 ✕ 移出后不再推送练习。</p>
        ${warehouse.map((v) => `
          <div class="m-list-item">
            <span>
              <strong>${escapeHtml(v.word)}</strong>
              <span class="m-muted">${escapeHtml(v.pronunciation || '')}</span>
              <span class="m-muted">${escapeHtml(v.translation || v.definition || '')}</span>
            </span>
            <span class="m-list-actions">
              ${speakBtnHtml(v.word, 'speak-btn-sm')}
              <button class="remove-btn speak-btn-sm" data-remove-vocab="${v.id}" type="button" aria-label="移出 ${escapeHtml(v.word)}" title="移出">✕</button>
            </span>
          </div>`).join('') || '<p class="m-muted">生词本是空的</p>'}
      </div>`;

    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
    $$('[data-remove-vocab]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          await api(`/api/vocab/${btn.dataset.removeVocab}`, { method: 'DELETE' });
          await loadVocab();
          toast('已移出生词本');
          renderVocab();
        } catch (e) { toast(e.message); }
      });
    });
  }

  /** FSRS review only: 会→Good(4), 不会→Again(1). Never delete the card here. */
  async function reviewDueCard(know) {
    const card = (state.due || [])[0];
    if (!card) return;
    try {
      // Frontend shows only 会/不会; finer FSRS state stays in DB.
      await api('/api/review', {
        method: 'POST',
        body: { vocab_id: card.id, rating: know ? 4 : 1 },
      });
      toast(know ? '会，已按计划延后' : '不会，稍后还会推送');
      await loadVocab();
      renderVocab();
    } catch (e) { toast(e.message); }
  }

  // ---------- PK ----------
  function pkAvatarMeta(name, index) {
    const palettes = ['pk-av-coral', 'pk-av-aqua', 'pk-av-sky', 'pk-av-lemon', 'pk-av-violet', 'pk-av-mint'];
    const bg = palettes[Math.abs(Number(index) || 0) % palettes.length];
    const short = (name || '?').trim().slice(0, 1) || '?';
    return { bg, short };
  }

  function pkPlayerRaceCard(p, { meId, total = 20, hostId, rank, mode = 'race' } = {}) {
    const isMe = p.user_id === meId;
    const online = isMe || p.online || p.is_bot;
    const av = pkAvatarMeta(p.name, p.user_id || rank || 0);
    const progress = Number(p.progress) || 0;
    const tot = Math.max(1, total || 20);
    let pct = 12;
    let meta = online ? '在线' : '离线';
    if (mode === 'lobby') {
      pct = p.ready ? 100 : 14;
      meta = p.ready ? '已准备' : (online ? '在线 · 未准备' : '离线');
    } else {
      pct = Math.min(100, Math.round((progress / tot) * 100));
      meta = p.finished ? '已完成全部题目' : `${progress}/${tot} 题`;
    }
    return `
      <div class="pk-racer ${isMe ? 'is-me' : ''} ${p.finished ? 'is-done' : ''} ${p.ready && mode === 'lobby' ? 'is-ready' : ''}">
        <div class="pk-racer-rank">${rank != null ? rank : '·'}</div>
        <div class="pk-avatar ${av.bg}" aria-hidden="true">${escapeHtml(av.short)}</div>
        <div class="pk-racer-body">
          <div class="pk-racer-top">
            <strong class="pk-racer-name">${escapeHtml(p.name)}${isMe ? ' · 我' : ''}</strong>
            <span class="pk-racer-score">${mode === 'lobby' ? (p.ready ? '✓' : '…') : (p.score ?? 0)}</span>
          </div>
          <div class="pk-racer-tags">
            ${p.user_id === hostId ? '<span class="pk-tag host">房主</span>' : ''}
            ${p.is_bot ? '<span class="pk-tag bot">机器人</span>' : ''}
            ${mode === 'lobby' && p.ready ? '<span class="pk-tag ready">就绪</span>' : ''}
            ${p.finished ? '<span class="pk-tag done">完成</span>' : ''}
          </div>
          <div class="pk-racer-bar"><i style="width:${pct}%"></i></div>
          <div class="pk-racer-meta">${escapeHtml(meta)}</div>
        </div>
      </div>`;
  }

  function renderPk() {
    const root = $('#view-pk');
    const room = state.pk.room;
    if (room?.status === 'playing') return renderPkPlay(root, room);
    if (room?.status === 'finished') return renderPkResult(root, room);

    const books = state.wordbooks || [];
    const meId = state.user?.id;
    const players = room?.players || [];
    const humans = players.filter((p) => !p.is_bot);
    const hasBot = players.some((p) => p.is_bot);
    const me = humans.find((p) => p.user_id === meId) || humans[0];
    const waitingLobby = room?.status === 'waiting';
    const canStart = humans.length >= 2 || hasBot;

    root.innerHTML = `
      <div class="m-hero pk-hero">
        <h1>单词对战</h1>
        <p>多人同题竞速 · 各自作答 · 全员完成后排名</p>
      </div>
      ${waitingLobby ? `
        <div class="pk-lobby">
          <div class="pk-code-card">
            <div class="pk-code-label">房间码 · 发给好友一起加入</div>
            <div class="pk-code-row">
              <span class="pk-code">${escapeHtml(room.code)}</span>
              <button class="m-btn m-btn-ghost" type="button" id="pkCopy">复制</button>
            </div>
            <div class="pk-code-count">${players.length} 人在房</div>
          </div>
          <div class="pk-racer-list">
            ${players.map((p, i) => pkPlayerRaceCard(p, {
              meId,
              total: 20,
              hostId: room.host_id,
              rank: i + 1,
              mode: 'lobby',
            })).join('')}
          </div>
          <p class="pk-hint">
            ${canStart
              ? (humans.every((p) => p.ready) ? '全员已准备，即将开始…' : '所有真人点「准备开战」后开始（可不限人数）')
              : '邀请好友加入，或先邀请机器人陪练'}
          </p>
          <div class="pk-actions">
            ${!hasBot ? `<button class="m-btn m-btn-sky m-btn-block" id="pkInviteBot" type="button">邀请机器人</button>` : ''}
            <button class="m-btn m-btn-sun m-btn-block" id="pkReady" type="button">
              ${me?.ready ? '已准备 ✓' : '准备开战'}
            </button>
            <button class="m-btn m-btn-ghost m-btn-block" id="pkLeave" type="button">退出房间</button>
          </div>
        </div>
      ` : `
        <div class="m-card">
          <h2>题库</h2>
          <select class="m-input" id="pkBook">
            <option value="">ECDICT随机词典</option>
            ${books.map((b) => `<option value="${b.id}" ${state.pk.wordbookId == b.id ? 'selected' : ''}>${escapeHtml(b.name)}</option>`).join('')}
          </select>
          <button class="m-btn m-btn-primary m-btn-block" id="pkCreate" type="button">创建房间</button>
          <p class="m-muted" style="margin:10px 0 0;font-size:0.88rem;">进房后可邀请机器人陪练，或分享房间码约好友。</p>
        </div>
        <div class="m-card">
          <h2>加入房间</h2>
          <input class="m-input" id="pkCode" placeholder="输入 6 位房间码" maxlength="8" autocomplete="off" />
          <button class="m-btn m-btn-mint m-btn-block" id="pkJoin" type="button">加入</button>
        </div>
      `}`;

    $('#pkBook')?.addEventListener('change', (e) => {
      state.pk.wordbookId = e.target.value ? Number(e.target.value) : null;
    });
    $('#pkCreate')?.addEventListener('click', () => startPk('pvp'));
    $('#pkJoin')?.addEventListener('click', joinPk);
    $('#pkInviteBot')?.addEventListener('click', async () => {
      try {
        const room2 = await api('/api/pk/rooms/invite-bot', {
          method: 'POST',
          body: { code: room.code },
        });
        state.pk.room = room2;
        renderPk();
        toast('已邀请机器人');
      } catch (e) { toast(e.message); }
    });
    $('#pkReady')?.addEventListener('click', () => {
      if (me?.ready) return toast('已准备');
      markPkReady(room.code);
    });
    $('#pkCopy')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(room.code);
        toast('房间码已复制');
      } catch (_) {
        toast(room.code);
      }
    });
    $('#pkLeave')?.addEventListener('click', leavePkRoom);
  }

  async function leavePkRoom() {
    const code = state.pk.room?.code;
    try {
      if (code) {
        await api('/api/pk/rooms/leave', { method: 'POST', body: { code } });
      }
    } catch (_) { /* ignore */ }
    try { state.pk.ws?.close(); } catch (_) {}
    state.pk.ws = null;
    state.pk.room = null;
    stopPkPoll();
    renderPk();
    toast('已退出房间');
  }

  function stopPkPoll() {
    if (state.pk.pollTimer) {
      clearInterval(state.pk.pollTimer);
      state.pk.pollTimer = null;
    }
  }

  function startPkPoll(code) {
    stopPkPoll();
    state.pk.pollTimer = setInterval(async () => {
      if (state.tab !== 'pk' || !state.pk.room || state.pk.room.code !== code) return;
      if (state.pk.room.status === 'finished') return stopPkPoll();
      try {
        const room = await api(`/api/pk/rooms/${encodeURIComponent(code)}`);
        state.pk.room = room;
        if (state.tab === 'pk') renderPk();
        if (room.status === 'finished') stopPkPoll();
      } catch (_) { /* room may expire */ }
    }, 2000);
  }

  async function startPk(mode = 'pvp') {
    try {
      const room = await api('/api/pk/rooms', {
        method: 'POST',
        body: { mode: mode === 'bot' ? 'bot' : 'pvp', wordbook_id: state.pk.wordbookId || null },
      });
      state.pk.room = room;
      connectPkWs(room.code);
      startPkPoll(room.code);
      renderPk();
      toast(`房间 ${room.code}，可邀请机器人或分享给好友`);
    } catch (e) { toast(e.message); }
  }

  async function joinPk() {
    const code = ($('#pkCode')?.value || '').trim().toUpperCase().replace(/[\s\-_]/g, '');
    if (!code) return toast('输入房间码');
    try {
      const room = await api('/api/pk/rooms/join', { method: 'POST', body: { code } });
      state.pk.room = room;
      connectPkWs(room.code);
      startPkPoll(room.code);
      renderPk();
      toast(`已加入 ${room.code}`);
    } catch (e) { toast(e.message); }
  }

  async function markPkReady(code) {
    ensurePkWs(code);
    try {
      // Prefer HTTP so ready works even if WS is still connecting (Render latency).
      const room = await api('/api/pk/rooms/ready', {
        method: 'POST',
        body: { code, ready: true },
      });
      state.pk.room = room;
      if (state.tab === 'pk') renderPk();
    } catch (e) {
      toast(e.message || '准备失败');
    }
    sendPkWs({ action: 'ready' });
  }

  function ensurePkWs(code) {
    const ws = state.pk.ws;
    if (ws && state.pk.wsCode === code && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    connectPkWs(code);
  }

  function sendPkWs(msg) {
    const payload = typeof msg === 'string' ? msg : JSON.stringify(msg);
    const ws = state.pk.ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(payload); } catch (_) {}
      return;
    }
    if (!state.pk.wsQueue) state.pk.wsQueue = [];
    state.pk.wsQueue.push(payload);
    if (state.pk.room?.code) ensurePkWs(state.pk.room.code);
  }

  function connectPkWs(code) {
    try { state.pk.ws?.close(); } catch (_) {}
    state.pk.wsCode = code;
    state.pk.wsQueue = state.pk.wsQueue || [];
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/api/pk/ws/${encodeURIComponent(code)}`);
    state.pk.ws = ws;
    ws.onopen = () => {
      const queued = state.pk.wsQueue || [];
      state.pk.wsQueue = [];
      try { ws.send(JSON.stringify({ action: 'ping' })); } catch (_) {}
      for (const item of queued) {
        try { ws.send(item); } catch (_) {}
      }
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data || '{}');
      if (msg.event === 'error') return toast(msg.data?.detail || 'PK 错误');
      if (msg.data) {
        state.pk.room = msg.data;
        if (msg.data.feedback) state.pk.feedback = msg.data.feedback;
      }
      if (msg.event === 'finished') {
        const n = (msg.data?.missed_words || []).length;
        if (n) toast(`${n} 个不会的词已进生词本`);
        refreshVocab().catch(() => {});
        stopPkPoll();
      }
      if (state.tab === 'pk') renderPk();
    };
    ws.onclose = () => {
      if (state.pk.ws === ws) state.pk.ws = null;
      if (state.pk.room?.code && state.pk.room.status !== 'finished') startPkPoll(state.pk.room.code);
    };
  }

  function renderPkPlay(root, room) {
    const meId = state.user?.id;
    const players = room.players || [];
    const me = players.find((p) => p.user_id === meId) || players.find((p) => !p.is_bot) || players[0];
    const q = room.question || {};
    const total = room.total || 20;
    const myIdx = (room.your_index ?? me?.current_index ?? 0);
    const feedback = state.pk.feedback;
    const waitingOthers = !!room.you_finished;
    const doneCount = players.filter((p) => p.finished).length;

    root.innerHTML = `
      <div class="pk-live-head">
        <div class="pk-live-title">多人竞速</div>
        <div class="pk-live-sub">${waitingOthers ? '你已答完，等待其他人…' : `第 ${Math.min(total, myIdx + 1)} / ${total} 题`} · ${doneCount}/${players.length} 人完成</div>
      </div>
      <div class="pk-racer-list pk-racer-list-live">
        ${players.map((p, i) => pkPlayerRaceCard(p, {
          meId,
          total,
          hostId: room.host_id,
          rank: i + 1,
          mode: 'race',
        })).join('')}
      </div>
      ${waitingOthers ? `
        <div class="pk-wait-card">
          <h2>你已交卷</h2>
          <p>得分 <strong>${room.your_score ?? me?.score ?? 0}</strong>。其他人答完后自动出排名。</p>
          <button class="m-btn m-btn-ghost m-btn-block" id="pkLeaveMid" type="button">退出房间</button>
        </div>
      ` : `
        <div class="pk-quiz-card">
          <div class="pk-quiz-label">看中文选英文</div>
          <p class="pk-quiz-prompt">${escapeHtml(q.prompt || '')}</p>
          <div class="pk-options" id="pkOptions">
            ${(q.options || []).map((opt, i) => {
              let cls = '';
              if (feedback && feedback.index === q.index) {
                if (i === feedback.correct) cls = 'correct';
                if (i === feedback.choice && !feedback.is_correct) cls = 'wrong';
              }
              const locked = !!(feedback && feedback.index === q.index);
              return `<div class="pk-option ${cls}" data-choice="${i}" role="button" tabindex="0"${locked ? ' aria-disabled="true"' : ''}>
                <span class="pk-opt-key">${String.fromCharCode(65 + i)}</span>
                <span class="pk-opt-text">${escapeHtml(opt)}</span>
                ${speakBtnHtml(opt, 'speak-btn-sm pk-opt-speak', { as: 'span' })}
              </div>`;
            }).join('')}
          </div>
          <button class="m-btn m-btn-ghost m-btn-block" id="pkLeaveMid" type="button" style="margin-top:12px;">退出房间</button>
        </div>
      `}`;

    $('#pkLeaveMid')?.addEventListener('click', leavePkRoom);
    $$('#pkOptions [data-choice]').forEach((row) => {
      row.onclick = (ev) => {
        if (ev.target.closest('[data-speak-word]')) return;
        if (row.getAttribute('aria-disabled') === 'true') return;
        state.pk.feedback = null;
        sendPkWs({ action: 'answer', choice: Number(row.dataset.choice) });
      };
    });

    if (feedback && feedback.index === q.index) {
      setTimeout(() => {
        if (state.pk.feedback === feedback) state.pk.feedback = null;
      }, 450);
    } else if (feedback && feedback.index !== q.index) {
      state.pk.feedback = null;
    }
  }

  function renderPkResult(root, room) {
    const missed = room.missed_words || [];
    const results = room.results || [];
    root.innerHTML = `
      <div class="m-hero pk-hero">
        <h1>对战结束</h1>
        <p>${missed.length ? `${missed.length} 个错词已进生词本` : '全部答对，太强了！'}</p>
      </div>
      <div class="pk-podium">
        ${results.slice(0, 3).map((r, i) => `
          <div class="pk-podium-slot place-${i + 1}">
            <div class="pk-podium-medal">${['🥇', '🥈', '🥉'][i]}</div>
            <div class="pk-podium-name">${escapeHtml(r.name)}</div>
            <div class="pk-podium-score">${r.score} 分</div>
          </div>`).join('')}
      </div>
      <div class="pk-racer-list">
        ${results.map((r, i) => pkPlayerRaceCard({
          ...r,
          progress: room.total || 20,
          finished: true,
          ready: true,
          online: true,
        }, {
          meId: state.user?.id,
          total: room.total || 20,
          hostId: room.host_id,
          rank: i + 1,
          mode: 'race',
        })).join('')}
      </div>
      ${missed.length ? `<div class="m-card"><h2>已进生词本</h2>
        ${missed.map((w) => `
          <div class="m-list-item">
            <span><strong>${escapeHtml(w.word)}</strong><span class="m-muted"> ${escapeHtml(w.translation || '')}</span></span>
            <span class="m-list-actions">
              ${speakBtnHtml(w.word, 'speak-btn-sm')}
              <span class="m-chip">生词</span>
            </span>
          </div>`).join('')}</div>` : ''}
      <button class="m-btn m-btn-primary m-btn-block" id="pkAgain" type="button">再来一局</button>`;
    $('#pkAgain').onclick = () => {
      state.pk.room = null;
      state.pk.feedback = null;
      try { state.pk.ws?.close(); } catch (_) {}
      state.pk.ws = null;
      stopPkPoll();
      renderPk();
    };
  }

  // ---------- Mine ----------
  function stopBookTranslatePoll() {
    if (state.bookTranslate.pollTimer) {
      clearInterval(state.bookTranslate.pollTimer);
      state.bookTranslate.pollTimer = null;
    }
  }

  function startBookTranslatePoll() {
    stopBookTranslatePoll();
    state.bookTranslate.pollTimer = setInterval(() => {
      if (state.tab !== 'mine') return;
      refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    }, 2000);
  }

  async function refreshBookTranslateStatus({ ensureCatalog = false } = {}) {
    const q = ensureCatalog ? '?ensure_catalog=true' : '';
    const data = await api(`/api/jobs/book-translate/status${q}`);
    state.bookTranslate.scan = data.scan || null;
    if (!state.bookTranslate.localRunning) {
      state.bookTranslate.progress = data.progress || state.bookTranslate.progress || null;
      state.bookTranslate.checkpoint = data.checkpoint || data.progress?.checkpoint || null;
      state.bookTranslate.resumable = !!data.resumable;
    }
    state.bookTranslate.running = !!data.running || !!state.bookTranslate.localRunning;
    if (data.running) startBookTranslatePoll();
    else if (!state.bookTranslate.localRunning) stopBookTranslatePoll();
    // Auto-chain server jobs if client asked for continuous mode (non-App fallback).
    if (
      state.bookTranslate.clientChain
      && !data.running
      && !state.bookTranslate.localRunning
      && Number(data.scan?.pending_books || 0) > 0
    ) {
      novelLog('I', 'server.chain_next', { pending: data.scan?.pending_books });
      api(
        '/api/jobs/book-translate/backfill?full_run=true&ensure_catalog=false&batch_size=15&max_books=1',
        { method: 'POST' },
      ).then(() => startBookTranslatePoll()).catch((e) => novelLog('E', 'server.chain_fail', String(e.message || e)));
    }
    if (state.tab === 'mine') {
      if (state.bookTranslate.localRunning) updateBookTranslateUi();
      else renderMine();
    }
    return data;
  }

  async function startBookTranslateJob() {
    const bt = state.bookTranslate;
    if (bt.running || bt.loading || bt.localRunning) return;
    const pending = Number(bt.scan?.pending_books || 0);
    const bridge = nativeBridge();
    const useLocal = !!(bridge && (typeof bridge.translateNovel === 'function' || typeof bridge.translateText === 'function'));

    novelLog('I', 'job.click', {
      pending,
      isApp: nativeApkMeta().isApp,
      useLocal,
      hasBridge: !!bridge,
      apk: nativeApkMeta(),
    });

    if (!pending && !bt.resumable && !useLocal) {
      toast('没有待译书籍');
      return;
    }

    // Reading module: prefer on-device claim/submit loop whenever native translate exists.
    if (useLocal || nativeApkMeta().isApp) {
      if (!useLocal) {
        toast('当前 App 缺少翻译接口，请更新 App');
        novelLog('E', 'job.no_translate_bridge');
        return;
      }
      await startLocalBookTranslateLoop();
      return;
    }

    // Browser fallback: server translate, but keep chaining until catalog done.
    bt.clientChain = true;
    bt.loading = true;
    bt.phase = 'translating';
    setTranslatePhase('translating', '服务端翻译进行中（网页模式）…');
    renderMine();
    try {
      await api(
        '/api/jobs/book-translate/backfill?full_run=true&ensure_catalog=true&batch_size=15&max_books=1',
        { method: 'POST' },
      );
      toast('已开始自动翻译，将逐本持续进行');
      await refreshBookTranslateStatus({ ensureCatalog: false });
      startBookTranslatePoll();
    } catch (e) {
      bt.clientChain = false;
      novelLog('E', 'job.server_start_fail', String(e.message || e));
      toast(e.message || '启动失败');
    } finally {
      bt.loading = false;
      if (state.tab === 'mine') renderMine();
    }
  }

  async function startLocalBookTranslateLoop() {
    const bt = state.bookTranslate;
    if (bt.localRunning) return;
    bt.localAbort = false;
    bt.clientChain = false;
    bt.localRunning = true;
    bt.loading = true;
    bt.running = true;
    bt.emptyClaimStreak = 0;
    bt.failStreak = 0;
    bt.phase = 'loading';
    novelLog('I', 'loop.start', { pending: bt.scan?.pending_books, engine: bt.engine, apk: nativeApkMeta() });
    renderMine();
    try {
      await ensureNovelModelReady();
      novelLog('I', 'model.ready', {
        engine: bt.engine,
        qwen: !!(nativeBridge() && typeof nativeBridge().isNovelQwenReady === 'function' && nativeBridge().isNovelQwenReady()),
      });
      toast(bt.engine === 'qwen_local' ? 'Qwen 离线翻译已启动，将自动译完全库' : '本地翻译已启动，将自动译完全库');
      bt.loading = false;
      bt.phase = 'translating';
      setTranslatePhase('translating', '开始逐段翻译…');

      let round = 0;
      while (!bt.localAbort) {
        round += 1;
        let claim;
        try {
          novelLog('I', 'claim.request', { round, limit: 3 });
          claim = await api('/api/jobs/book-translate/claim?limit=3&ensure_catalog=true', {
            method: 'POST',
          });
        } catch (e) {
          bt.failStreak = (bt.failStreak || 0) + 1;
          novelLog('E', 'claim.error', { round, err: String(e.message || e), failStreak: bt.failStreak });
          setTranslatePhase('translating', `领取失败，重试中(${bt.failStreak})…`);
          if (bt.failStreak >= 12) {
            toast('领取失败次数过多，已暂停（可再点继续）');
            break;
          }
          await new Promise((r) => setTimeout(r, Math.min(8000, 600 * bt.failStreak)));
          continue;
        }
        bt.failStreak = 0;
        novelLog('I', 'claim.result', {
          round,
          done: !!claim.done,
          ok: claim.ok,
          items: (claim.items || []).length,
          book: claim.book_key,
          title: claim.title,
          progress: `${claim.translated_blocks || 0}/${claim.block_count || 0}`,
          message: claim.message || '',
        });

        if (claim.done) {
          novelLog('I', 'loop.done', claim.message || '全部完成');
          toast(claim.message || '全部翻译完成');
          break;
        }

        if (!claim.items || !claim.items.length) {
          bt.emptyClaimStreak = (bt.emptyClaimStreak || 0) + 1;
          novelLog('W', 'claim.empty_skip', { streak: bt.emptyClaimStreak, message: claim.message });
          setTranslatePhase('translating', `暂无段落，自动跳过重试(${bt.emptyClaimStreak})…`);
          if (bt.emptyClaimStreak >= 8) {
            await refreshBookTranslateStatus({ ensureCatalog: true }).catch(() => {});
            const pendingNow = Number(bt.scan?.pending_books || 0);
            novelLog('W', 'claim.empty_rescan', { pending: pendingNow });
            if (!pendingNow) {
              toast('全部翻译完成');
              break;
            }
            bt.emptyClaimStreak = 0;
          }
          await new Promise((r) => setTimeout(r, 700));
          continue;
        }
        bt.emptyClaimStreak = 0;

        bt.currentTitle = claim.title || claim.book_key || '';
        setTranslatePhase(
          'translating',
          `正在翻译：${bt.currentTitle} · 段 ${claim.translated_blocks || 0}/${claim.block_count || '?'} · 已完成书 ${bt.scan?.done_books || 0}/${bt.scan?.total_books || '?'}`,
        );

        const batch = [];
        for (const item of claim.items) {
          if (bt.localAbort) break;
          const enPreview = String(item.en_text || '').slice(0, 80);
          novelLog('I', 'para.translate.start', {
            book: item.book_key,
            order: item.order_index,
            enLen: (item.en_text || '').length,
            en: enPreview,
          });
          try {
            const zh = await translateNovelParagraph(item.en_text);
            if (zh) {
              batch.push({
                edition_id: item.edition_id,
                order_index: item.order_index,
                en_text: item.en_text,
                zh_text: zh,
              });
              novelLog('I', 'para.translate.ok', {
                order: item.order_index,
                zhLen: zh.length,
                engine: bt.engine,
                zh: zh.slice(0, 60),
              });
              setTranslatePhase(
                'translating',
                `已译段 #${item.order_index} · ${bt.currentTitle} · 已完成书 ${bt.scan?.done_books || 0}`,
              );
            } else {
              novelLog('W', 'para.translate.empty', { order: item.order_index, engine: bt.engine });
            }
          } catch (e) {
            novelLog('E', 'para.translate.fail', { order: item.order_index, err: String(e.message || e) });
          }
          await new Promise((r) => setTimeout(r, 200));
        }

        if (bt.localAbort) {
          novelLog('I', 'loop.abort_by_user', { round });
          break;
        }

        if (!batch.length) {
          novelLog('W', 'batch.empty', { round, claimed: (claim.items || []).length });
          await new Promise((r) => setTimeout(r, 900));
          continue;
        }

        const source = bt.engine === 'qwen_local' ? 'qwen_local' : (bt.engine || 'mlkit_fallback');
        try {
          novelLog('I', 'submit.request', { count: batch.length, source, book: bt.currentTitle });
          const submitted = await api('/api/jobs/book-translate/submit', {
            method: 'POST',
            body: { items: batch, source },
          });
          novelLog('I', 'submit.ok', {
            saved: submitted.saved,
            skipped: submitted.skipped,
            status: submitted.translate_status,
            progress: `${submitted.translated_blocks}/${submitted.block_count}`,
            doneBooks: submitted.scan?.done_books,
            pendingBooks: submitted.scan?.pending_books,
          });
          if (submitted.scan) bt.scan = submitted.scan;
          setTranslatePhase(
            'translating',
            `已落库 +${submitted.saved || 0} · ${submitted.title || bt.currentTitle} ${submitted.translated_blocks || 0}/${submitted.block_count || '?'} · 已完成书 ${submitted.scan?.done_books || 0}/${submitted.scan?.total_books || '?'}`,
          );
        } catch (e) {
          bt.failStreak = (bt.failStreak || 0) + 1;
          novelLog('E', 'submit.error', { err: String(e.message || e), failStreak: bt.failStreak });
          if (bt.failStreak >= 12) {
            toast('提交失败次数过多，已暂停（可再点继续）');
            break;
          }
          await new Promise((r) => setTimeout(r, 1000));
          continue;
        }
        await new Promise((r) => setTimeout(r, 300));
      }
    } catch (e) {
      novelLog('E', 'loop.fatal', String(e.message || e));
      toast(e.message || '本地翻译失败');
    } finally {
      novelLog('I', 'loop.end', {
        abort: !!bt.localAbort,
        doneBooks: bt.scan?.done_books,
        pending: bt.scan?.pending_books,
      });
      bt.localRunning = false;
      bt.running = false;
      bt.loading = false;
      bt.modelPercent = null;
      bt.phase = 'idle';
      await refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
      if (state.tab === 'mine') renderMine();
    }
  }

  function stopLocalBookTranslate() {
    novelLog('I', 'loop.stop_requested');
    state.bookTranslate.localAbort = true;
    state.bookTranslate.clientChain = false;
    setTranslatePhase('stopping', '正在停止翻译…');
    toast('正在停止…');
  }

  function renderMine() {
    const u = state.user || {};
    const bt = state.bookTranslate;
    const scan = bt.scan || {};
    const pending = Number(scan.pending_books || 0);
    const doneBooks = Number(scan.done_books || 0);
    const totalBooks = Number(scan.total_books || 0);
    const isApp = nativeApkMeta().isApp;
    const running = !!(bt.running || bt.localRunning);
    const resumable = !!bt.resumable && !running;
    const percent = (typeof bt.modelPercent === 'number')
      ? bt.modelPercent
      : (totalBooks ? Math.round((doneBooks / totalBooks) * 100) : Math.max(0, Number(bt.progress?.percent || 0)));
    const engineHint = bt.engine
      ? (bt.engine === 'qwen_local' ? 'Qwen 本地' : bt.engine === 'mlkit_fallback' ? '兼容引擎' : bt.engine)
      : (isApp || nativeBridge() ? 'App 离线译' : '网页服务端');
    let statusLine = totalBooks ? '点击继续翻译开始' : '点击下方扫描经典书架';
    if (bt.phase === 'downloading' || typeof bt.modelPercent === 'number') {
      statusLine = `正在下载小说翻译模型 ${bt.modelPercent ?? 0}%（约1GB）`;
    } else if (bt.phase === 'loading') {
      statusLine = bt.progress?.message || '正在加载本地翻译引擎…';
    } else if (running) {
      statusLine = bt.progress?.message || `正在逐段翻译 · 已完成 ${doneBooks}/${totalBooks} 本`;
    } else if (pending) {
      statusLine = `待译 ${pending} 本 · 已完成 ${doneBooks} 本（整本译完才 +1）`;
    } else if (totalBooks) {
      statusLine = '全部书籍已翻译完成';
    }
    const cta = running ? '停止翻译' : (bt.phase === 'downloading' ? '下载模型中…' : (bt.loading ? '启动中…' : (resumable || pending ? '继续翻译' : '开始翻译')));
    const apk = nativeApkMeta();
    const ver = cachedAppVersion;
    const webLabel = localWebVersion() || ver?.web_content_version || '—';
    const apkLabel = apk.isApp || nativeBridge()
      ? `${apk.name || 'App'} (${apk.code || 0})`
      : '网页版';
    const curTitle = bt.currentTitle || bt.progress?.current_title || '';

    $('#view-mine').innerHTML = `
      <div class="m-hero"><h1>我的</h1><p>账号与阅读偏好</p></div>
      <div class="m-card novel-log-card" id="novelLogCard">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;">
          <h2 style="margin:0;font-size:1.05rem;">翻译调试日志</h2>
          <button class="m-btn m-btn-ghost" id="copyNovelLogBtn" type="button" style="padding:4px 10px;font-size:0.78rem;">复制日志</button>
        </div>
        <p class="m-muted" style="margin:0 0 8px;font-size:0.78rem;">点「继续翻译」后这里会实时滚动输出。若为空说明还在用旧缓存页面。</p>
        <pre id="novelTranslateLog" class="novel-translate-log">${escapeHtml((bt.logs || []).slice(-120).join('\n') || '等待开始翻译…')}</pre>
      </div>
      <div class="m-card">
        <div style="display:flex;align-items:center;gap:14px;">
          <div class="m-logo" style="width:56px;height:56px;font-size:1.6rem;border-radius:20px;">🫧</div>
          <div>
            <h2 style="margin:0;">${escapeHtml(u.username || '学员')}</h2>
            <p class="m-muted" style="margin:4px 0 0;">已登录 · 单词泡泡学员</p>
          </div>
        </div>
      </div>
      <div class="m-card">
        <h2 style="margin:0 0 6px;">版本更新</h2>
        <p class="m-muted" style="margin:0 0 10px;">网页补丁自动下发；原生壳有新包时再安装。</p>
        <p class="m-muted" style="margin:0 0 12px;font-size:0.82rem;">当前网页 ${escapeHtml(webLabel)} · App ${escapeHtml(apkLabel)}</p>
        <button class="m-btn m-btn-primary m-btn-block" id="checkUpdateBtn" type="button">检测最新版本</button>
      </div>
      <div class="m-card book-translate-card">
        <h2 style="margin:0 0 6px;">经典书库翻译</h2>
        <p class="m-muted" style="margin:0;">一人离线译 · 结果共享 · ${escapeHtml(engineHint)}</p>
        <p id="btPhaseHint" class="m-muted" style="margin:6px 0 0;font-size:0.78rem;">阶段:${escapeHtml(bt.phase || 'idle')} · 引擎:${escapeHtml(bt.engine || '未启动')}</p>
        <div class="bt-stats">
          <span>待译 <strong id="btPendingBooks">${pending}</strong></span>
          <span>已完成 <strong id="btDoneBooks">${doneBooks}</strong></span>
          <span>共 <strong id="btTotalBooks">${totalBooks}</strong></span>
        </div>
        <div class="progress-bar-wrap bt-progress"><div class="progress-bar" id="btProgressBar" style="width:${percent}%"></div></div>
        <div class="bt-status" id="btStatusLine">${escapeHtml(statusLine)}</div>
        <div class="m-muted" id="btCurrentLine" style="margin-top:6px;${curTitle && running ? '' : 'display:none;'}">当前：${escapeHtml(curTitle)}</div>
        <div class="bt-actions">
          <button class="m-btn m-btn-ghost" id="scanBooksBtn" type="button" ${running || bt.loading ? 'disabled' : ''}>扫描待译</button>
          <button class="m-btn m-btn-primary" id="startTranslateBtn" type="button" ${bt.phase === 'downloading' || (bt.loading && !running) ? 'disabled' : ''}>
            ${cta}
          </button>
        </div>
      </div>
      <div class="m-card">
        <button class="m-btn m-btn-ghost m-btn-block" id="toggleEyeMine" type="button">护眼模式：${state.eyecare ? '开' : '关'}</button>
        ${state.shell?.supports_login ? '<a class="m-btn m-btn-sky m-btn-block" href="/login?next=/app&mode=login" style="margin-top:8px;text-align:center;display:block;">切换账号</a>' : ''}
        ${state.shell?.supports_login ? '<button class="m-btn m-btn-danger m-btn-block" id="logoutBtn" type="button" style="margin-top:8px;">退出登录</button>' : ''}
      </div>`;
    $('#toggleEyeMine').onclick = () => { state.eyecare = !state.eyecare; applyEyecare(); renderMine(); };
    $('#logoutBtn')?.addEventListener('click', async () => {
      await api('/api/auth/logout', { method: 'POST' });
      location.href = '/login?next=/app';
    });
    $('#checkUpdateBtn')?.addEventListener('click', () => checkForUpdate());
    $('#scanBooksBtn')?.addEventListener('click', async () => {
      try {
        toast('扫描中…');
        await refreshBookTranslateStatus({ ensureCatalog: true });
        toast(`待译 ${state.bookTranslate.scan?.pending_books || 0} 本 · 已完成 ${state.bookTranslate.scan?.done_books || 0} 本`);
      } catch (e) { toast(e.message); }
    });
    $('#startTranslateBtn')?.addEventListener('click', () => {
      if (state.bookTranslate.localRunning || state.bookTranslate.clientChain) {
        stopLocalBookTranslate();
        return;
      }
      startBookTranslateJob();
    });
    $('#copyNovelLogBtn')?.addEventListener('click', () => copyNovelLogs());
  }

  $('#userBtn').addEventListener('click', () => setTab('mine'));
  $$('#tabNav button').forEach((btn) => btn.addEventListener('click', () => setTab(btn.dataset.tab)));

  // Capture phase so speak works even inside PK option rows.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-speak-word]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const word = btn.getAttribute('data-speak-word') || btn.dataset.speakWord || '';
    // Avoid focus-driven scrollIntoView jump on mobile WebView.
    if (typeof btn.focus === 'function') {
      try { btn.focus({ preventScroll: true }); } catch (_) {}
    }
    try { btn.blur(); } catch (_) {}
    speakWord(word);
  }, true);

  async function boot() {
    applyEyecare();
    if (!(await ensureAuth())) return;
    try {
      await Promise.all([loadReadings(), loadBooks(), loadVocab()]);
    } catch (e) { console.warn(e); }
    fetchAppVersion().catch(() => {});
    refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    setTab('read');
  }
  boot();
})();
