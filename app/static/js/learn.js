// ── 学习页：/learn?id= ──────────────────────────────
const params = new URLSearchParams(location.search);
const learnVideoId = parseInt(params.get('id') || '0', 10);

const videoPlayer = document.getElementById('videoPlayer');
const learnTitle = document.getElementById('learnTitle');
const learnMeta = document.getElementById('learnMeta');
const subtitleList = document.getElementById('subtitleList');
const subtitleCount = document.getElementById('subtitleCount');
const statusMsg = document.getElementById('statusMsg');
const wordModal = document.getElementById('wordModal');
const wordModalBody = document.getElementById('wordModalBody');
const saveWordBtn = document.getElementById('saveWordBtn');
const phaseBadge = document.getElementById('phaseBadge');
const learnPhaseTip = document.getElementById('learnPhaseTip');
const onlyUnknownToggle = document.getElementById('onlyUnknownToggle');
const autoPauseToggle = document.getElementById('autoPauseToggle');
const repeatLineBtn = document.getElementById('repeatLineBtn');
const syncHint = document.getElementById('syncHint');
const subtitleWindowMeta = document.getElementById('subtitleWindowMeta');

let activeWord = '';
let currentSubtitles = [];
let currentVideoId = null;
let currentVideoSource = '';
let currentVideoMeta = {};
let currentLearnPhase = 'metadataReady';
let refreshTimer = null;
let activeLookupSeq = 0;
let savedWords = new Set();
let onlyUnknownMode = false;
let autoPauseEnabled = false;
let lastAutoPausedIdx = -1;
let subtitleRenderQueued = false;
let subtitleRenderForceNext = false;
let subtitleWindowState = {
  start: 0,
  end: 0,
  total: 0,
  modeKey: '',
  renderedIds: [],
  windowed: false,
};
let translationFocusTimer = null;
let lastTranslationFocusKey = '';

const LONG_SUBTITLE_THRESHOLD = 320;
const LONG_SUBTITLE_WINDOW = 140;
const LONG_SUBTITLE_WINDOW_MARGIN = 24;

// ── 视频时间追踪 ──
// YouTube: 使用官方 YouTube IFrame Player API (https://developers.google.com/youtube/iframe_api_reference)
// Bilibili: 使用 postMessage + 时间估算回退
let ytPlayer = null;          // YouTube IFrame API Player 实例
let ytApiReady = false;       // YouTube API 是否已加载
let videoSync = {
  interval: null,
  isPlaying: false,
  // Bilibili 时间估算
  biliBaseTime: 0,        // 当前播放位置（秒）
  biliLastUpdate: 0,      // 上次更新时间戳（ms）
  biliPaused: true,       // 是否暂停
  biliSynced: false,      // 是否已从某个时间点同步启动
  activeIdx: -1,          // 当前高亮的字幕索引
  videoDuration: 0,       // 视频总时长（秒）
  isDragging: false,      // 是否正在拖拽进度条
};

// ── 进度条元素 ──
const progressBar = document.getElementById('progressBar');
const progressFilled = document.getElementById('progressFilled');
const progressBuffer = document.getElementById('progressBuffer');
const timeDisplay = document.getElementById('timeDisplay');

// ── 进度条拖拽事件 ──
if (progressBar) {
  // 开始拖拽
  progressBar.addEventListener('pointerdown', (e) => {
    videoSync.isDragging = true;
    progressBar.setPointerCapture(e.pointerId);
  });

  // 拖拽中：实时更新字幕高亮
  progressBar.addEventListener('input', (e) => {
    const pct = parseFloat(progressBar.value);
    const seekTime = videoSync.videoDuration > 0
      ? (pct / 100) * videoSync.videoDuration
      : 0;
    // 更新进度条填充
    if (progressFilled) progressFilled.style.width = pct + '%';
    // 更新时间显示
    if (timeDisplay) {
      timeDisplay.textContent = `${formatTime(seekTime)} / ${formatTime(videoSync.videoDuration)}`;
    }
    // 拖拽时实时高亮字幕
    highlightSubtitle(seekTime);
  });

  // 释放：执行跳转
  progressBar.addEventListener('pointerup', (e) => {
    if (!videoSync.isDragging) return;
    videoSync.isDragging = false;
    progressBar.releasePointerCapture(e.pointerId);
    const pct = parseFloat(progressBar.value);
    const seekTime = videoSync.videoDuration > 0
      ? (pct / 100) * videoSync.videoDuration
      : 0;
    jumpToTime(seekTime);
  });

  // 兜底：如果 pointerup 在元素外触发
  progressBar.addEventListener('pointercancel', () => {
    videoSync.isDragging = false;
  });
}

// ── 更新进度条 UI ──
function updateProgressBar(currentTime, duration) {
  if (videoSync.isDragging) return; // 拖拽中不更新，避免冲突
  if (duration > 0) {
    videoSync.videoDuration = duration;
    if (progressBar) progressBar.max = 100;
    const pct = (currentTime / duration) * 100;
    if (progressBar) progressBar.value = pct;
    if (progressFilled) progressFilled.style.width = pct + '%';
  }
  if (timeDisplay) {
    timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
  }
}

async function api(url, options = {}, timeoutMs = 0) {
  const controller = new AbortController();
  let timer = null;
  if (timeoutMs > 0) {
    timer = setTimeout(() => controller.abort(), timeoutMs);
  }
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || resp.statusText);
    }
    return resp.json();
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function showStatus(msg, type = '') {
  statusMsg.textContent = msg;
  statusMsg.className = 'status-msg ' + type;
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function lookupSourceLabel(source) {
  const map = {
    wordbook: '词书',
    vocab: '生词缓存',
    'online-cache': '本地缓存',
    core_en: '内置词典',
    miss: '本地未命中',
  };
  return map[source] || source || '本地词典';
}

function renderWordDetails(data) {
  const zh = data.translation || data.youdao_translation || data.definition || '暂无本地释义';
  const suggestions = Array.isArray(data.suggestions) && data.suggestions.length
    ? `<div class="word-info-row"><span class="word-label">近似词</span><span>${data.suggestions.map((item) => `<button type="button" class="word-suggestion-chip" data-suggest-word="${item}">${item}</button>`).join(' ')}</span></div>`
    : '';
  wordModalBody.innerHTML = `
    <h3>${data.word}</h3>
    <div class="word-source-inline">${lookupSourceLabel(data.lookup_source)}</div>
    <div class="word-info">
      <div class="word-info-row"><span class="word-label">音标</span><span>${data.pronunciation || '暂无'}</span></div>
      <div class="word-info-row"><span class="word-label">优先译义</span><span>${zh}</span></div>
      <div class="word-info-row"><span class="word-label">英文释义</span><span>${data.definition || '暂无'}</span></div>
      <div class="word-info-row"><span class="word-label">词性</span><span>${data.part_of_speech || '暂无'}</span></div>
      ${data.example ? `<div class="word-info-row"><span class="word-label">例句</span><span>${data.example}</span></div>` : ''}
      ${suggestions}
    </div>
    <div class="word-enrich-hint">本次查词已命中本地词典，未使用在线翻译。</div>
  `;
}

function learnPhaseMeta(phase) {
  const map = {
    metadataReady: { label: '准备中', cls: 'pending', tip: '正在解析视频与字幕元信息' },
    subtitleReady: { label: '可跟读', cls: 'processing', tip: '英文字幕已就绪，中文正在后台补全' },
    translationStreaming: { label: '补译中', cls: 'processing', tip: '可以先学，译文会持续流式补上' },
    reviewReady: { label: '可复习', cls: 'done', tip: '字幕与译文都已就绪，可直接沉浸学习' },
    failed: { label: '无字幕', cls: 'failed', tip: '当前视频没有可提取字幕或抓取失败' },
  };
  return map[phase] || map.metadataReady;
}

function setLearnPhase(phase, message = '') {
  currentLearnPhase = phase || 'metadataReady';
  if (currentVideoMeta) currentVideoMeta.learn_phase = currentLearnPhase;
  const meta = learnPhaseMeta(phase);
  if (phaseBadge) {
    phaseBadge.textContent = meta.label;
    phaseBadge.className = `status-badge ${meta.cls}`;
  }
  if (learnPhaseTip) {
    learnPhaseTip.textContent = message || meta.tip;
  }
}

function extractLookupWords(text) {
  return String(text || '')
    .split(/(\s+)/)
    .map((part) => part.replace(/[^A-Za-z'-]/g, '').split("'")[0].replace(/[^A-Za-z]/g, '').toLowerCase())
    .filter(Boolean);
}

function subtitleHasUnknownWords(seg) {
  const words = extractLookupWords(seg?.text || '');
  if (!words.length) return true;
  return words.some((word) => !savedWords.has(word));
}

function getVisibleSubtitles() {
  if (!onlyUnknownMode) return currentSubtitles;
  return currentSubtitles.filter(subtitleHasUnknownWords);
}

function isLongSubtitleMode(subtitles) {
  return (subtitles || []).length > LONG_SUBTITLE_THRESHOLD;
}

function getActiveSubtitleId() {
  return currentSubtitles[videoSync.activeIdx]?.id || null;
}

function subtitleModeKey(subtitles) {
  return `${onlyUnknownMode ? 'unknown' : 'all'}:${subtitles.length}`;
}

function resolveSubtitleWindow(subtitles, force = false) {
  const total = subtitles.length;
  const modeKey = subtitleModeKey(subtitles);
  if (!isLongSubtitleMode(subtitles)) {
    return {
      items: subtitles,
      start: 0,
      end: total,
      total,
      modeKey,
      windowed: false,
      renderedIds: subtitles.map((seg) => seg.id),
    };
  }

  const activeId = getActiveSubtitleId();
  const activeVisibleIdx = activeId ? subtitles.findIndex((seg) => seg.id === activeId) : -1;
  const canReuseWindow = (
    !force &&
    subtitleWindowState.windowed &&
    subtitleWindowState.modeKey === modeKey &&
    subtitleWindowState.total === total &&
    activeVisibleIdx >= 0 &&
    activeVisibleIdx >= subtitleWindowState.start + LONG_SUBTITLE_WINDOW_MARGIN &&
    activeVisibleIdx < subtitleWindowState.end - LONG_SUBTITLE_WINDOW_MARGIN
  );

  if (canReuseWindow) {
    const start = Math.max(0, Math.min(subtitleWindowState.start, total));
    const end = Math.max(start, Math.min(subtitleWindowState.end, total));
    const items = subtitles.slice(start, end);
    return {
      items,
      start,
      end,
      total,
      modeKey,
      windowed: true,
      renderedIds: items.map((seg) => seg.id),
    };
  }

  let anchorIdx = activeVisibleIdx;
  if (anchorIdx < 0 && !force && subtitleWindowState.modeKey === modeKey && subtitleWindowState.total === total) {
    const currentSize = Math.max(1, subtitleWindowState.end - subtitleWindowState.start);
    anchorIdx = Math.min(
      total - 1,
      subtitleWindowState.start + Math.floor(currentSize / 2),
    );
  }
  if (anchorIdx < 0) anchorIdx = 0;

  const leading = Math.floor(LONG_SUBTITLE_WINDOW * 0.35);
  let start = Math.max(0, anchorIdx - leading);
  let end = Math.min(total, start + LONG_SUBTITLE_WINDOW);
  start = Math.max(0, end - LONG_SUBTITLE_WINDOW);
  const items = subtitles.slice(start, end);
  return {
    items,
    start,
    end,
    total,
    modeKey,
    windowed: true,
    renderedIds: items.map((seg) => seg.id),
  };
}

function updateSubtitleWindowMeta(meta, visibleTotal) {
  if (!subtitleWindowMeta) return;
  if (!meta.windowed) {
    subtitleWindowMeta.textContent = '';
    subtitleWindowMeta.classList.add('hidden');
    return;
  }
  const translatedCount = meta.items.filter((seg) => seg.translation).length;
  const unit = onlyUnknownMode ? '待学句' : '字幕';
  subtitleWindowMeta.textContent =
    `长视频模式：当前只渲染第 ${meta.start + 1}-${meta.end} 条${unit}（共 ${visibleTotal} 条），中文优先补这一段。当前窗口已补 ${translatedCount}/${meta.items.length} 条。`;
  subtitleWindowMeta.classList.remove('hidden');
}

function requestSubtitleRender(force = false) {
  if (force) subtitleRenderForceNext = true;
  if (subtitleRenderQueued) return;
  subtitleRenderQueued = true;
  requestAnimationFrame(() => {
    subtitleRenderQueued = false;
    const nextForce = subtitleRenderForceNext;
    subtitleRenderForceNext = false;
    renderSubtitles(getVisibleSubtitles(), { force: nextForce });
  });
}

function keepSubtitleInView(item) {
  if (!item || !subtitleList) return;
  const top = item.offsetTop;
  const bottom = top + item.offsetHeight;
  const visibleTop = subtitleList.scrollTop + 72;
  const visibleBottom = subtitleList.scrollTop + subtitleList.clientHeight - 72;
  if (top < visibleTop || bottom > visibleBottom) {
    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function patchSubtitleTranslation(subtitleId, translation) {
  const sub = currentSubtitles.find((item) => item.id === subtitleId);
  if (!sub) return;
  sub.translation = translation;
  const textNode = subtitleList.querySelector(`.subtitle-item[data-id="${subtitleId}"] .subtitle-text-zh`);
  if (textNode) {
    const pending = !translation && currentLearnPhase !== 'reviewReady' && currentLearnPhase !== 'failed';
    textNode.textContent = translation || (pending ? '中文补译中...' : '');
    textNode.classList.toggle('pending', pending);
  }
  if (subtitleWindowState.windowed && subtitleWindowState.renderedIds.includes(subtitleId)) {
    const items = subtitleWindowState.renderedIds
      .map((id) => currentSubtitles.find((item) => item.id === id))
      .filter(Boolean);
    updateSubtitleWindowMeta({
      ...subtitleWindowState,
      items,
    }, getVisibleSubtitles().length);
  }
}

function queueTranslationFocus() {
  if (translationFocusTimer) clearTimeout(translationFocusTimer);
  translationFocusTimer = setTimeout(pushTranslationFocus, 280);
}

async function pushTranslationFocus() {
  translationFocusTimer = null;
  if (!currentVideoId || !subtitleWindowState.renderedIds.length) return;
  if (!['subtitleReady', 'translationStreaming'].includes(currentLearnPhase)) return;

  const subtitleIds = subtitleWindowState.renderedIds
    .filter((id) => {
      const seg = currentSubtitles.find((item) => item.id === id);
      return seg && !seg.translation;
    })
    .slice(0, 80);
  if (!subtitleIds.length) return;

  const anchorId = getActiveSubtitleId() || subtitleIds[0];
  const focusKey = `${currentVideoId}:${anchorId}:${subtitleIds.join(',')}`;
  if (focusKey === lastTranslationFocusKey) return;
  lastTranslationFocusKey = focusKey;

  try {
    await api(`/api/videos/${currentVideoId}/translation-focus`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anchor_id: anchorId, subtitle_ids: subtitleIds }),
    }, 3000);
  } catch (_) {}
}

async function loadSavedWords() {
  try {
    const items = await api('/api/vocab');
    savedWords = new Set((items || []).map((item) => String(item.word || '').toLowerCase()).filter(Boolean));
  } catch (_) {
    savedWords = new Set();
  }
}

function playerCanAutoControl() {
  return currentVideoSource === 'youtube';
}

function pausePlayback() {
  if (currentVideoSource === 'bilibili') {
    pauseBiliPlayback();
    return;
  }
  if (ytPlayer && ytPlayer.pauseVideo) {
    try {
      ytPlayer.pauseVideo();
    } catch (_) {}
  }
}

function repeatActiveLine() {
  const seg = currentSubtitles[videoSync.activeIdx];
  if (!seg) return;
  lastAutoPausedIdx = -1;
  jumpToTime(seg.start);
}

function getEstimatedBiliTime() {
  if (!videoSync.biliSynced) return 0;
  if (!videoSync.isPlaying) return videoSync.biliBaseTime || 0;
  const elapsed = Math.max(0, (Date.now() - (videoSync.biliLastUpdate || Date.now())) / 1000);
  return (videoSync.biliBaseTime || 0) + elapsed;
}

function withTimeParam(url, sec, autoplay = false) {
  if (!url) return url;
  const safeSec = Math.max(0, Math.floor(sec));
  try {
    const target = new URL(url);
    target.searchParams.set('t', String(safeSec));
    if (autoplay) target.searchParams.set('autoplay', '1');
    else target.searchParams.delete('autoplay');
    return target.toString();
  } catch (_) {
    const joiner = url.includes('?') ? '&' : '?';
    return `${url}${joiner}t=${safeSec}${autoplay ? '&autoplay=1' : ''}`;
  }
}

function buildSourceUrlAtTime(sec) {
  const base = currentVideoMeta?.url || '';
  if (!base) return '';
  const safeSec = Math.max(0, Math.floor(sec));
  try {
    const target = new URL(base);
    target.searchParams.set('t', String(safeSec));
    return target.toString();
  } catch (_) {
    const joiner = base.includes('?') ? '&' : '?';
    return `${base}${joiner}t=${safeSec}`;
  }
}

function updateBiliControls() {
  const controls = document.getElementById('playerControls');
  if (!controls || currentVideoSource !== 'bilibili') return;
  controls.classList.remove('hidden');
  if (playPauseBtn) {
    playPauseBtn.textContent = videoSync.isPlaying ? '⏸ 暂停并同步' : '▶ 从当前继续';
  }
  if (repeatLineBtn) {
    repeatLineBtn.disabled = !currentSubtitles.length;
  }
}

function renderBiliPlayer(startSec = 0, autoplay = false) {
  if (!currentVideoMeta?.embed_url) return;
  const embedUrl = withTimeParam(currentVideoMeta.embed_url, startSec, autoplay);
  videoPlayer.innerHTML = `<iframe id="biliPlayerFrame" src="${embedUrl}" allowfullscreen frameborder="0" allow="autoplay; encrypted-media; picture-in-picture" style="width:100%;height:100%;"></iframe>`;
}

function updateBiliHint() {
  if (!syncHint || currentVideoSource !== 'bilibili') return;
  const sec = Math.max(0, Math.floor(getEstimatedBiliTime()));
  const humanTime = formatTime(sec);
  const sourceUrl = buildSourceUrlAtTime(sec);
  syncHint.classList.remove('hidden');
  syncHint.innerHTML = `
    <div><strong>B站学习模式</strong>：点击右侧字幕会把播放器重载到对应秒数并开始播放。如果你手动暂停、拖动或切集，请再点一次“重新同步”。</div>
    <div class="sync-hint-actions">
      <button type="button" class="btn-secondary btn-sm" data-bili-action="sync-start">从头同步</button>
      <button type="button" class="btn-secondary btn-sm" data-bili-action="sync-current">按当前高亮句重新同步</button>
      ${sourceUrl ? `<a class="btn-secondary btn-sm" href="${sourceUrl}" target="_blank" rel="noreferrer">在B站原页打开 ${humanTime}</a>` : ''}
      <span class="sync-hint-time">当前估算：${humanTime}</span>
    </div>
  `;
}

function syncBiliToTime(sec, autoplay = true) {
  const safeSec = Math.max(0, Number(sec) || 0);
  renderBiliPlayer(safeSec, autoplay);
  videoSync.biliBaseTime = safeSec;
  videoSync.biliLastUpdate = Date.now();
  videoSync.biliPaused = !autoplay;
  videoSync.isPlaying = !!autoplay;
  videoSync.biliSynced = true;
  highlightSubtitle(safeSec);
  updateProgressBar(safeSec, videoSync.videoDuration || (currentSubtitles[currentSubtitles.length - 1]?.end || 0));
  updateBiliControls();
  updateBiliHint();
}

function pauseBiliPlayback() {
  const currentTime = getEstimatedBiliTime();
  renderBiliPlayer(currentTime, false);
  videoSync.biliBaseTime = currentTime;
  videoSync.biliLastUpdate = Date.now();
  videoSync.biliPaused = true;
  videoSync.isPlaying = false;
  videoSync.biliSynced = true;
  updateProgressBar(currentTime, videoSync.videoDuration || (currentSubtitles[currentSubtitles.length - 1]?.end || 0));
  updateBiliControls();
  updateBiliHint();
}

function resumeBiliPlayback() {
  const currentTime = getEstimatedBiliTime() || currentSubtitles[videoSync.activeIdx]?.start || 0;
  syncBiliToTime(currentTime, true);
}

// ── 初始化学习页 ──
async function initLearnPage() {
  if (!learnVideoId) {
    showStatus('缺少视频 ID', 'error');
    return;
  }
  try {
    await loadSavedWords();
    const video = await api(`/api/videos/${learnVideoId}`);
    currentVideoId = video.id;
    currentVideoSource = video.source;
    currentVideoMeta = video;
    lastTranslationFocusKey = '';
    setLearnPhase(video.learn_phase, video.status_message || '');
    videoSync.biliSynced = false;
    videoSync.isPlaying = false;
    if (syncHint) {
      syncHint.classList.toggle('hidden', video.source !== 'bilibili');
    }
    if (autoPauseToggle) {
      autoPauseToggle.disabled = !playerCanAutoControl();
      autoPauseToggle.checked = false;
    }
    if (repeatLineBtn) {
      repeatLineBtn.disabled = !(playerCanAutoControl() || video.source === 'bilibili');
    }

    learnTitle.textContent = video.title || video.url;
    learnMeta.innerHTML = `
      <span>${video.source}</span>
      <span>${video.subtitle_count || 0} 条字幕</span>
      <span>${video.subtitle_status}</span>
      ${video.duration_seconds ? `<span>${Math.round(video.duration_seconds)} 秒</span>` : ''}
    `;

    if (video.embed_url) {
      if (video.source === 'youtube') {
        let embedUrl = video.embed_url;
        if (!embedUrl.includes('enablejsapi=1')) {
          embedUrl += (embedUrl.includes('?') ? '&' : '?') + 'enablejsapi=1';
        }
        videoPlayer.innerHTML = `<iframe id="ytPlayer" src="${embedUrl}" allowfullscreen frameborder="0" allow="autoplay; encrypted-media"></iframe>`;
        initYouTubePlayer();
      } else {
        renderBiliPlayer(0, false);
        updateBiliControls();
        startBiliSyncHint();
      }
    }

    if (video.duration_seconds) {
      videoSync.videoDuration = video.duration_seconds;
    }

    if (video.subtitle_count > 0 && ['ready', 'done', 'translating'].includes(video.subtitle_status)) {
      const subs = await api(`/api/videos/${learnVideoId}/subtitles`);
      currentSubtitles = subs;
      renderSubtitles(getVisibleSubtitles(), { force: true });
      if (video.subtitle_status === 'translating' || video.subtitle_status === 'ready') {
        showStatus('可以开始学习，中文翻译后台进行中', 'success');
        subscribeTranslationUpdates(learnVideoId);
        queueTranslationFocus();
      } else {
        showStatus('字幕已就绪，开始学习吧', 'success');
      }
      startSubtitleSyncLoop();
    } else if (video.subtitle_status === 'processing' || video.subtitle_status === 'pending') {
      showStatus(video.status_message || '后台处理中...', 'loading');
      loadSubtitles(learnVideoId);
    } else {
      showStatus(video.status_message || '暂无字幕', 'error');
      loadSubtitles(learnVideoId);
    }
  } catch (e) {
    showStatus('加载失败: ' + e.message, 'error');
  }
}

function subscribeTranslationUpdates(videoId) {
  if (subtitleEventSource) {
    subtitleEventSource.close();
  }
  subtitleEventSource = new EventSource(`/api/videos/${videoId}/subtitles/stream`);
  subtitleEventSource.addEventListener('translated', (e) => {
    const data = JSON.parse(e.data);
    patchSubtitleTranslation(data.id, data.translation);
  });
  subtitleEventSource.addEventListener('done', (e) => {
    try {
      const data = JSON.parse(e.data);
      setLearnPhase(data.phase || 'reviewReady', '字幕与译文已就绪');
    } catch (_) {}
    requestSubtitleRender(true);
    showStatus('字幕翻译完成', 'success');
    subtitleEventSource?.close();
    subtitleEventSource = null;
  });
}

function startBiliSyncHint() {
  updateBiliControls();
  updateBiliHint();
  showStatus('B站模式已启用：点击右侧字幕即可从该句开始同步学习', 'loading');
}

function startSubtitleSyncLoop() {
  if (videoSync.interval) clearInterval(videoSync.interval);
  videoSync.interval = setInterval(() => {
    if (!currentSubtitles.length) return;
    if (ytPlayer && ytPlayer.getCurrentTime) {
      try {
        const t = ytPlayer.getCurrentTime();
        highlightSubtitle(t);
        if (autoPauseEnabled) maybeAutoPause(t);
        updateProgressBar(t, ytPlayer.getDuration() || videoSync.videoDuration);
      } catch (_) {}
      return;
    }
    if (currentVideoSource === 'bilibili' && videoSync.biliSynced) {
      const t = getEstimatedBiliTime();
      highlightSubtitle(t);
      updateProgressBar(t, videoSync.videoDuration || (currentSubtitles[currentSubtitles.length - 1]?.end || 0));
      updateBiliHint();
    }
  }, 150);
}
// ── 加载字幕（SSE 增量推送，无需轮询）──
let subtitleEventSource = null;

function loadSubtitles(videoId) {
  if (subtitleEventSource) {
    subtitleEventSource.close();
    subtitleEventSource = null;
  }
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }

  // 重置字幕列表
  currentSubtitles = [];
  lastTranslationFocusKey = '';
  if (translationFocusTimer) clearTimeout(translationFocusTimer);
  subtitleWindowState = { start: 0, end: 0, total: 0, modeKey: '', renderedIds: [], windowed: false };
  subtitleList.innerHTML = '';
  subtitleCount.textContent = '';
  subtitleWindowMeta?.classList.add('hidden');
  showStatus('正在获取字幕...', 'loading');

  subtitleEventSource = new EventSource(`/api/videos/${videoId}/subtitles/stream`);

  // 状态变更
  subtitleEventSource.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
    setLearnPhase(data.phase || 'metadataReady', data.message || '');
    showStatus(data.message, data.status === 'done' ? 'success' : 'loading');
  });

  // 单条新增字幕（增量）
  subtitleEventSource.addEventListener('subtitle', (e) => {
    const sub = JSON.parse(e.data);
    // 避免重复添加
    if (currentSubtitles.some(s => s.id === sub.id)) return;
    currentSubtitles.push(sub);
    currentSubtitles.sort((a, b) => a.start - b.start);
    // 从最后一条字幕估算视频时长
    if (!videoSync.videoDuration && currentSubtitles.length > 0) {
      videoSync.videoDuration = currentSubtitles[currentSubtitles.length - 1].end || 0;
    }
    requestSubtitleRender();
  });

  // 单条翻译完成（增量更新）
  subtitleEventSource.addEventListener('translated', (e) => {
    const data = JSON.parse(e.data);
    patchSubtitleTranslation(data.id, data.translation);
    const translatedCount = currentSubtitles.filter(s => s.translation).length;
    showStatus(`翻译进行中... ${translatedCount}/${currentSubtitles.length}`, 'loading');
  });

  // 完成 / 可学习
  subtitleEventSource.addEventListener('ready', (e) => {
    const data = JSON.parse(e.data);
    setLearnPhase(data.phase || 'subtitleReady', data.message || '可以开始学习');
    requestSubtitleRender(true);
    queueTranslationFocus();
    showStatus('可以开始学习了！', 'success');
    startSubtitleSyncLoop();
    if (currentSubtitles.length === 0 && data.total) {
      subtitleCount.textContent = `${data.total} 条`;
    }
  });

  // 完成
  subtitleEventSource.addEventListener('done', (e) => {
    const data = JSON.parse(e.data);
    setLearnPhase(data.phase || (currentSubtitles.length > 0 ? 'reviewReady' : 'failed'), data.message || '');
    requestSubtitleRender(true);
    if (currentSubtitles.length > 0) {
      const translatedCount = currentSubtitles.filter(s => s.translation).length;
      showStatus(translatedCount === currentSubtitles.length ? '字幕加载完成！' : '字幕加载完成（部分未翻译）', 'success');
      startSubtitleSyncLoop();
    } else {
      showStatus(data.message || '该视频没有可用字幕', 'error');
      const durationMinutes = Math.round((currentVideoMeta?.duration_seconds || 0) / 60);
      const longVideoTip = durationMinutes > 10
        ? `当前视频约 ${durationMinutes} 分钟。超长无字幕内容不适合本地整段识别，建议优先换有 CC/AI 字幕版本，或拆成短片段后再学。`
        : '你看到的「中字」若是画面里烧进去的硬字幕，B站 API 无法提取。请换播放器右下角有 CC/AI 字幕开关的视频，或尝试较短视频的语音识别。';
      subtitleList.innerHTML = `<div class="empty-state"><h3>暂无字幕</h3><p>${data.message || '该视频可能没有 AI/CC 字幕轨道。'}</p><p style="color:var(--muted);font-size:13px">${longVideoTip}</p><div class="empty-state-actions"><button class="btn-primary" id="refetchSubsBtn" style="margin-top:12px">重新获取字幕</button>${currentVideoMeta?.url ? `<a class="btn-secondary" href="${currentVideoMeta.url}" target="_blank" rel="noreferrer" style="margin-top:12px">打开原视频</a>` : ''}</div></div>`;
      document.getElementById('refetchSubsBtn')?.addEventListener('click', () => {
        api(`/api/videos/${videoId}/refetch`, { method: 'POST' }).then(() => loadSubtitles(videoId));
      });
    }
    subtitleEventSource.close();
    subtitleEventSource = null;
  });

  // 错误
  subtitleEventSource.addEventListener('error', (e) => {
    if (e.data) {
      try {
        const data = JSON.parse(e.data);
        showStatus(data.message || '字幕获取失败', 'error');
      } catch (_) {
        showStatus('字幕获取失败', 'error');
      }
    }
  });

  // SSE 连接断开时：若已有字幕则保留，否则尝试 REST 拉取
  subtitleEventSource.onerror = () => {
    if (currentSubtitles.length > 0) return;
    api(`/api/videos/${videoId}/subtitles`).then(subs => {
      if (subs.length) {
        currentSubtitles = subs;
        renderSubtitles(getVisibleSubtitles(), { force: true });
        showStatus(`已加载 ${subs.length} 条字幕`, 'success');
      }
    }).catch(() => {});
  };
}

function renderSubtitles(subtitles, options = {}) {
  subtitleCount.textContent = onlyUnknownMode ? `${subtitles.length} 条待学句` : `${subtitles.length} 条`;
  subtitleList.innerHTML = '';

  if (!subtitles.length) {
    subtitleWindowState = { start: 0, end: 0, total: 0, modeKey: '', renderedIds: [], windowed: false };
    subtitleWindowMeta?.classList.add('hidden');
    subtitleList.innerHTML = '<div class="empty-state"><p>当前过滤条件下没有待学句，试试关闭“仅看待学句”。</p></div>';
    return;
  }

  const meta = resolveSubtitleWindow(subtitles, !!options.force);
  subtitleWindowState = {
    start: meta.start,
    end: meta.end,
    total: meta.total,
    modeKey: meta.modeKey,
    renderedIds: meta.renderedIds,
    windowed: meta.windowed,
  };
  updateSubtitleWindowMeta(meta, subtitles.length);

  const fragment = document.createDocumentFragment();
  meta.items.forEach((seg, idx) => {
    const item = document.createElement('div');
    const unknown = subtitleHasUnknownWords(seg);
    const pendingZh = !seg.translation && currentLearnPhase !== 'reviewReady' && currentLearnPhase !== 'failed';
    item.className = `subtitle-item${unknown ? ' subtitle-item-unknown' : ''}`;
    item.dataset.index = meta.start + idx;
    item.dataset.id = seg.id;
    item.dataset.start = seg.start;
    item.dataset.end = seg.end;

    const enHtml = seg.text.split(/(\s+)/).map(part => {
      if (!part.trim()) return part;
      const clean = part.replace(/[^A-Za-z'-]/g, '');
      if (!clean) return part;
      const lookupWord = clean.split("'")[0].replace(/[^A-Za-z]/g, '');
      if (!lookupWord) return part;
      return `<span class="clickable-word" data-word="${lookupWord}">${part}</span>`;
    }).join('');

    item.innerHTML = `
      <div class="subtitle-time">${formatTime(seg.start)} → ${formatTime(seg.end)}</div>
      <div class="subtitle-text-en">${enHtml}</div>
      <div class="subtitle-text-zh${pendingZh ? ' pending' : ''}">${seg.translation || (pendingZh ? '中文补译中...' : '')}</div>
    `;

    item.addEventListener('click', (e) => {
      const wordEl = e.target.closest('.clickable-word');
      if (wordEl) {
        e.stopPropagation();
        loadWord(wordEl.dataset.word);
      }
    });

    item.addEventListener('click', () => {
      jumpToTime(seg.start);
    });

    fragment.appendChild(item);
  });

  subtitleList.appendChild(fragment);

  const activeId = getActiveSubtitleId();
  if (activeId) {
    const active = subtitleList.querySelector(`.subtitle-item[data-id="${activeId}"]`);
    if (active) active.classList.add('active');
  }

  queueTranslationFocus();
}

// ── YouTube IFrame Player API (官方库) ──
// 文档: https://developers.google.com/youtube/iframe_api_reference
// 通过 script 标签加载官方 API，无需 npm
function loadYouTubeIframeAPI() {
  if (ytApiReady || document.getElementById('yt-iframe-api')) return;
  const tag = document.createElement('script');
  tag.id = 'yt-iframe-api';
  tag.src = 'https://www.youtube.com/iframe_api';
  document.head.appendChild(tag);
}

// API 就绪后的全局回调（YouTube API 会自动调用此函数）
function onYouTubeIframeAPIReady() {
  ytApiReady = true;
  // 如果已有 iframe，初始化 Player
  if (document.getElementById('ytPlayer')) {
    initYouTubePlayer();
  }
}

function initYouTubePlayer() {
  if (!ytApiReady) {
    loadYouTubeIframeAPI();
    return;  // API 加载后会自动调用 onYouTubeIframeAPIReady
  }
  if (ytPlayer) {
    // 已有 Player 实例，先销毁
    try { ytPlayer.destroy(); } catch(e) {}
    ytPlayer = null;
  }
  // 用官方 API 创建 Player，接管已有 iframe
  ytPlayer = new YT.Player('ytPlayer', {
    events: {
      'onReady': onYTPlayerReady,
      'onStateChange': onYTPlayerStateChange,
    }
  });
}

function onYTPlayerReady(event) {
  // 获取视频总时长
  try {
    videoSync.videoDuration = ytPlayer.getDuration() || 0;
  } catch(e) {}

  // 显示播放控制栏
  const controls = document.getElementById('playerControls');
  if (controls) controls.classList.remove('hidden');

  // 启动字幕同步轮询 (200ms = 5fps)
  if (videoSync.interval) clearInterval(videoSync.interval);
  videoSync.activeIdx = -1;
  videoSync.interval = setInterval(() => {
    if (!ytPlayer || !ytPlayer.getCurrentTime || !currentSubtitles.length) return;
    try {
      const time = ytPlayer.getCurrentTime();
      const state = ytPlayer.getPlayerState();
      // state: 1=playing, 2=paused, 0=ended, 3=buffering, 5=cued
      videoSync.isPlaying = (state === 1);
      if (time !== undefined && !isNaN(time)) {
        highlightSubtitle(time);
        if (autoPauseEnabled) maybeAutoPause(time);
        // 更新进度条
        const duration = ytPlayer.getDuration() || videoSync.videoDuration;
        updateProgressBar(time, duration);
      }
    } catch(e) {}
  }, 200);
}

function onYTPlayerStateChange(event) {
  // 1=playing, 2=paused, 0=ended
  videoSync.isPlaying = (event.data === 1);
}

// ── 视频跳转 ──
function jumpToTime(sec) {
  lastAutoPausedIdx = -1;
  if (currentVideoSource === 'bilibili') {
    syncBiliToTime(sec, true);
    return;
  }
  // YouTube: 使用官方 API
  if (ytPlayer && ytPlayer.seekTo) {
    try {
      ytPlayer.seekTo(sec, true);
      ytPlayer.playVideo();
      const duration = ytPlayer.getDuration() || videoSync.videoDuration;
      updateProgressBar(sec, duration);
      return;
    } catch(e) {}
  }
  // Bilibili iframe 无法通过 JS 控制跳转，只高亮字幕
  highlightSubtitle(sec);
}

// ── Bilibili 字幕同步引擎 ──
// 使用 HTML5 <video> 元素，直接读取 currentTime 和播放状态
function startVideoSync(source) {
  if (videoSync.interval) clearInterval(videoSync.interval);

  // 重置状态
  videoSync.isPlaying = false;
  videoSync.biliBaseTime = 0;
  videoSync.biliLastUpdate = 0;
  videoSync.biliPaused = true;
  videoSync.activeIdx = -1;

  if (source !== 'bilibili') return;

  // 隐藏同步提示（HTML5 video 可直接控制，不需要手动同步）
  const hint = document.getElementById('syncHint');
  if (hint) hint.classList.add('hidden');

  // 等待 video 元素加载
  setTimeout(() => {
    const biliVideo = document.getElementById('biliPlayer');
    if (!biliVideo) return;

    // 监听 loadedmetadata 获取视频时长
    biliVideo.addEventListener('loadedmetadata', () => {
      videoSync.videoDuration = biliVideo.duration || 0;
      const btn = document.getElementById('playPauseBtn');
      if (btn) btn.textContent = '▶ 播放';
    });

    // 监听播放/暂停事件更新按钮状态
    biliVideo.addEventListener('play', () => {
      videoSync.biliPaused = false;
      videoSync.biliLastUpdate = Date.now();
      const btn = document.getElementById('playPauseBtn');
      if (btn) btn.textContent = '⏸ 暂停';
      const hint = document.getElementById('syncHint');
      if (hint) hint.classList.add('hidden');
    });

    biliVideo.addEventListener('pause', () => {
      videoSync.biliPaused = true;
      if (videoSync.biliLastUpdate > 0) {
        const elapsed = (Date.now() - videoSync.biliLastUpdate) / 1000;
        videoSync.biliBaseTime += elapsed;
      }
      const btn = document.getElementById('playPauseBtn');
      if (btn) btn.textContent = '▶ 播放';
    });

    biliVideo.addEventListener('ended', () => {
      videoSync.biliPaused = true;
      const btn = document.getElementById('playPauseBtn');
      if (btn) btn.textContent = '▶ 播放';
    });

    // 启动轮询 (200ms = 5fps, 足够流畅的高亮)
    videoSync.interval = setInterval(() => {
      if (!currentSubtitles.length) return;

      // 直接从 video 元素读取当前时间
      const currentTime = biliVideo.currentTime || 0;
      const duration = biliVideo.duration || videoSync.videoDuration || (currentSubtitles[currentSubtitles.length - 1]?.end || 0);
      
      if (duration > 0) {
        videoSync.videoDuration = duration;
      }
      
      highlightSubtitle(currentTime);
      updateProgressBar(currentTime, duration);
    }, 200);
  }, 500);
}

function maybeAutoPause(currentTime) {
  if (!autoPauseEnabled || !videoSync.isPlaying) return;
  const seg = currentSubtitles[videoSync.activeIdx];
  if (!seg) return;
  if (currentTime >= Math.max(seg.start, seg.end - 0.06) && lastAutoPausedIdx !== videoSync.activeIdx) {
    lastAutoPausedIdx = videoSync.activeIdx;
    pausePlayback();
  }
}

function highlightSubtitle(currentTime) {
  if (!currentSubtitles.length) return;

  // 二分查找当前时间对应的字幕（比线性遍历快）
  let activeIdx = -1;
  let lo = 0, hi = currentSubtitles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const seg = currentSubtitles[mid];
    if (currentTime < seg.start) {
      hi = mid - 1;
    } else if (currentTime >= seg.end) {
      lo = mid + 1;
    } else {
      activeIdx = mid;
      break;
    }
  }

  // 只在高亮索引变化时更新 DOM（避免每 200ms 重复操作）
  if (activeIdx === videoSync.activeIdx) return;
  videoSync.activeIdx = activeIdx;
  if (activeIdx >= 0 && activeIdx !== lastAutoPausedIdx) {
    lastAutoPausedIdx = -1;
  }

  const items = subtitleList.querySelectorAll('.subtitle-item');
  items.forEach(item => item.classList.remove('active'));

  if (activeIdx >= 0 && currentSubtitles[activeIdx]) {
    const activeId = currentSubtitles[activeIdx].id;
    let active = subtitleList.querySelector(`.subtitle-item[data-id="${activeId}"]`);
    if (!active && isLongSubtitleMode(getVisibleSubtitles())) {
      renderSubtitles(getVisibleSubtitles(), { force: true });
      active = subtitleList.querySelector(`.subtitle-item[data-id="${activeId}"]`);
    }
    if (!active) return;
    active.classList.add('active');
    keepSubtitleInView(active);
    queueTranslationFocus();
  }
}

// ── 单词查询 ──
async function loadWord(word) {
  if (!word) return;
  const lookupSeq = ++activeLookupSeq;
  try {
    wordModal.classList.remove('hidden');
    wordModalBody.innerHTML = '<div class="word-popover-loading">本地查词中...</div>';
    const fastData = await api(`/api/word-fast/${encodeURIComponent(word)}`);
    if (lookupSeq !== activeLookupSeq) return;
    activeWord = fastData.word;
    renderWordDetails(fastData);
    wordModal.classList.remove('hidden');
  } catch (e) {
    showStatus('查词失败: ' + e.message, 'error');
  }
}

function closeWordModal() {
  wordModal.classList.add('hidden');
}

// ── 保存生词 ──
async function saveWord() {
  if (!activeWord) return;
  try {
    const activeSeg = currentSubtitles[videoSync.activeIdx] || currentSubtitles[0];
    const payload = {
      word: activeWord,
      source_platform: currentVideoSource,
      source_video_id: currentVideoMeta.video_id || String(currentVideoId),
      source_url: currentVideoMeta.url || '',
      source_title: currentVideoMeta.title || '',
      sentence: activeSeg?.text || '',
      sentence_translation: activeSeg?.translation || '',
      timestamp: activeSeg?.start ?? 0,
    };
    const saved = await api('/api/vocab/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    savedWords.add(String(saved.word || activeWord).toLowerCase());
    lastTranslationFocusKey = '';
    renderSubtitles(getVisibleSubtitles(), { force: true });
    showStatus(`"${saved.word}" 已加入生词本`, 'success');
    closeWordModal();
  } catch (e) {
    showStatus('保存失败: ' + e.message, 'error');
  }
}

// ── 事件绑定 ──
saveWordBtn.addEventListener('click', saveWord);
wordModalBody.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-suggest-word]');
  if (!btn) return;
  loadWord(btn.dataset.suggestWord);
});

const playPauseBtn = document.getElementById('playPauseBtn');
if (playPauseBtn) {
  playPauseBtn.addEventListener('click', () => {
    if (currentVideoSource === 'bilibili') {
      if (videoSync.isPlaying) pauseBiliPlayback();
      else resumeBiliPlayback();
      return;
    }
    if (ytPlayer && ytPlayer.getPlayerState) {
      try {
        const state = ytPlayer.getPlayerState();
        if (state === 1) ytPlayer.pauseVideo();
        else ytPlayer.playVideo();
      } catch (_) {}
    }
  });
}

syncHint?.addEventListener('click', (e) => {
  const action = e.target.closest('[data-bili-action]')?.dataset.biliAction;
  if (!action) return;
  if (action === 'sync-start') {
    syncBiliToTime(0, true);
  } else if (action === 'sync-current') {
    const sec = currentSubtitles[videoSync.activeIdx]?.start ?? getEstimatedBiliTime();
    syncBiliToTime(sec, true);
  }
});

onlyUnknownToggle?.addEventListener('change', () => {
  onlyUnknownMode = !!onlyUnknownToggle.checked;
  lastTranslationFocusKey = '';
  renderSubtitles(getVisibleSubtitles(), { force: true });
});

autoPauseToggle?.addEventListener('change', () => {
  autoPauseEnabled = !!autoPauseToggle.checked;
  lastAutoPausedIdx = -1;
});

repeatLineBtn?.addEventListener('click', repeatActiveLine);

window.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
  if (e.key === ' ' && (playerCanAutoControl() || currentVideoSource === 'bilibili')) {
    e.preventDefault();
    playPauseBtn?.click();
  } else if ((e.key === 'r' || e.key === 'R') && (playerCanAutoControl() || currentVideoSource === 'bilibili')) {
    e.preventDefault();
    repeatActiveLine();
  } else if ((e.key === 's' || e.key === 'S') && !wordModal.classList.contains('hidden')) {
    e.preventDefault();
    saveWord();
  }
});

window.addEventListener('load', initLearnPage);