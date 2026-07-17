// ── 主页：视频学习 ──────────────────────────────────
const loadBtn = document.getElementById('loadBtn');
const videoUrlInput = document.getElementById('videoUrl');
const contentArea = document.getElementById('contentArea');
const videoPlayer = document.getElementById('videoPlayer');
const videoMeta = document.getElementById('videoMeta');
const subtitleList = document.getElementById('subtitleList');
const subtitleCount = document.getElementById('subtitleCount');
const statusMsg = document.getElementById('statusMsg');
const wordModal = document.getElementById('wordModal');
const wordModalBody = document.getElementById('wordModalBody');
const saveWordBtn = document.getElementById('saveWordBtn');

let activeWord = '';
let currentSubtitles = [];
let currentVideoId = null;
let currentVideoSource = '';
let currentVideoMeta = {};
let refreshTimer = null;
let activeLookupSeq = 0;

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

// ── 加载视频 ──
async function loadVideo() {
  const url = videoUrlInput.value.trim();
  if (!url) return;

  showStatus('正在解析视频链接...', 'loading');
  loadBtn.disabled = true;

  try {
    const video = await api('/api/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    currentVideoId = video.id;
    currentVideoSource = video.source;
    currentVideoMeta = video;

    // 渲染播放器
    if (video.embed_url) {
      if (video.source === 'youtube') {
        // YouTube: 使用官方 IFrame Player API
        let embedUrl = video.embed_url;
        if (!embedUrl.includes('enablejsapi=1')) {
          embedUrl += (embedUrl.includes('?') ? '&' : '?') + 'enablejsapi=1';
        }
        videoPlayer.innerHTML = `<iframe id="ytPlayer" src="${embedUrl}" allowfullscreen frameborder="0" allow="autoplay; encrypted-media; picture-in-picture"></iframe>`;
        initYouTubePlayer();
      } else {
        // Bilibili: 直接用 B站官方 embed iframe 播放
        // 不走后端代理视频流，直接利用B站CDN
        videoPlayer.innerHTML = `<iframe src="${video.embed_url}" allowfullscreen frameborder="0" allow="autoplay; encrypted-media; picture-in-picture" style="width:100%;height:100%;"></iframe>`;
        // B站 iframe 无法通过 JS 控制播放/暂停/跳转，隐藏自定义控制栏
        // 字幕同步改为基于时间估算
      }
    } else {
      videoPlayer.innerHTML = `<div class="empty-state"><p>无法嵌入此视频播放器</p></div>`;
    }

    videoMeta.innerHTML = `
      <span>来源: ${video.source}</span>
      <span>ID: ${video.video_id || 'N/A'}</span>
      <span>创建: ${new Date(video.created_at).toLocaleString()}</span>
    `;

    showStatus('视频已加载，正在获取字幕...', 'loading');
    contentArea.classList.remove('hidden');
    // 字幕请求不设超时（Whisper ASR 可能需要 2 分钟）
    // 不 await，让字幕加载和播放器渲染并行进行
    loadSubtitles(video.id);
  } catch (e) {
    showStatus('加载失败: ' + e.message, 'error');
  } finally {
    loadBtn.disabled = false;
  }
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
  subtitleList.innerHTML = '';
  subtitleCount.textContent = '';
  showStatus('正在获取字幕...', 'loading');

  subtitleEventSource = new EventSource(`/api/videos/${videoId}/subtitles/stream`);

  // 状态变更
  subtitleEventSource.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
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
    renderSubtitles(currentSubtitles);
    subtitleCount.textContent = `${currentSubtitles.length} 条`;
  });

  // 单条翻译完成（增量更新）
  subtitleEventSource.addEventListener('translated', (e) => {
    const data = JSON.parse(e.data);
    const sub = currentSubtitles.find(s => s.id === data.id);
    if (sub) {
      sub.translation = data.translation;
      renderSubtitles(currentSubtitles);
      const translatedCount = currentSubtitles.filter(s => s.translation).length;
      showStatus(`翻译进行中... ${translatedCount}/${currentSubtitles.length}`, 'loading');
    }
  });

  // 完成
  subtitleEventSource.addEventListener('done', (e) => {
    const data = JSON.parse(e.data);
    if (currentSubtitles.length > 0) {
      const translatedCount = currentSubtitles.filter(s => s.translation).length;
      showStatus(translatedCount === currentSubtitles.length ? '字幕加载完成！' : '字幕加载完成（部分未翻译）', 'success');
    } else {
      showStatus(data.message || '该视频没有可用字幕', 'error');
      subtitleList.innerHTML = `<div class="empty-state"><h3>暂无字幕</h3><p>${data.message || '该视频可能没有 AI/CC 字幕轨道。'}</p><p style="color:var(--muted);font-size:13px">你看到的「中字」若是画面里烧进去的硬字幕，B站 API 无法提取。请换播放器右下角有 CC/AI 字幕开关的视频，例如：<br><code>https://www.bilibili.com/video/BV1GJ411x7h7</code></p><button class="btn-primary" id="refetchSubsBtn" style="margin-top:12px">重新获取字幕</button></div>`;
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
        renderSubtitles(subs);
        showStatus(`已加载 ${subs.length} 条字幕`, 'success');
      }
    }).catch(() => {});
  };
}

function renderSubtitles(subtitles) {
  subtitleCount.textContent = `${subtitles.length} 条`;
  subtitleList.innerHTML = '';

  subtitles.forEach((seg, idx) => {
    const item = document.createElement('div');
    item.className = 'subtitle-item';
    item.dataset.index = idx;
    item.dataset.start = seg.start;
    item.dataset.end = seg.end;

    // 将英文文本中的单词变成可点击的
    const enHtml = seg.text.split(/(\s+)/).map(part => {
      if (!part.trim()) return part;
      // 提取纯字母部分作为查词关键词（去除撇号后的缩写后缀，如 What's → What）
      const clean = part.replace(/[^A-Za-z'-]/g, '');
      if (!clean) return part;
      // 缩写处理：What's → what, don't → don, I'll → I
      const lookupWord = clean.split("'")[0].replace(/[^A-Za-z]/g, '');
      if (!lookupWord) return part;
      return `<span class="clickable-word" data-word="${lookupWord}">${part}</span>`;
    }).join('');

    item.innerHTML = `
      <div class="subtitle-time">${formatTime(seg.start)} → ${formatTime(seg.end)}</div>
      <div class="subtitle-text-en">${enHtml}</div>
      <div class="subtitle-text-zh">${seg.translation || ''}</div>
    `;

    // 点击单词
    item.addEventListener('click', (e) => {
      const wordEl = e.target.closest('.clickable-word');
      if (wordEl) {
        e.stopPropagation();
        loadWord(wordEl.dataset.word);
      }
    });

    // 点击字幕项跳转视频
    item.addEventListener('click', () => {
      jumpToTime(seg.start);
    });

    subtitleList.appendChild(item);
  });
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

  const items = subtitleList.querySelectorAll('.subtitle-item');
  items.forEach(item => item.classList.remove('active'));

  if (activeIdx >= 0 && items[activeIdx]) {
    const active = items[activeIdx];
    active.classList.add('active');
    // 平滑滚动到当前字幕
    active.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
      source_url: currentVideoMeta.url || videoUrlInput.value.trim(),
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
    showStatus(`"${saved.word}" 已加入生词本`, 'success');
    closeWordModal();
  } catch (e) {
    showStatus('保存失败: ' + e.message, 'error');
  }
}

// ── 事件绑定 ──
loadBtn.addEventListener('click', loadVideo);
saveWordBtn.addEventListener('click', saveWord);
wordModalBody.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-suggest-word]');
  if (!btn) return;
  loadWord(btn.dataset.suggestWord);
});
videoUrlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') loadVideo();
});

// Bilibili 播放控制按钮
// B站 iframe 无法通过 JS 控制播放/暂停，只对 YouTube 生效
const playPauseBtn = document.getElementById('playPauseBtn');
if (playPauseBtn) {
  playPauseBtn.addEventListener('click', () => {
    // YouTube 播放控制
    if (ytPlayer && ytPlayer.getPlayerState) {
      try {
        const state = ytPlayer.getPlayerState();
        if (state === 1) {
          ytPlayer.pauseVideo();
        } else {
          ytPlayer.playVideo();
        }
        return;
      } catch(e) {}
    }
  });
}

// 页面加载时不需要启动同步，在 loadVideo 中启动

// ── Bilibili 扫码登录 ──────────────────────────────
const biliLoginBtn = document.getElementById('biliLoginBtn');
const biliLoginModal = document.getElementById('biliLoginModal');
const biliQrcodeArea = document.getElementById('biliQrcodeArea');
const biliLoginStatus = document.getElementById('biliLoginStatus');
const biliGenerateBtn = document.getElementById('biliGenerateBtn');

let biliPollTimer = null;
let biliQrcodeInstance = null;

// 页面加载时检查登录状态
checkBiliLoginStatus();

async function checkBiliLoginStatus() {
  if (!biliLoginBtn) return;
  try {
    const result = await api('/api/bili/login/status');
    if (result.valid) {
      biliLoginBtn.textContent = `✓ ${result.username}`;
      biliLoginBtn.classList.add('logged-in');
    } else {
      biliLoginBtn.textContent = 'B站登录';
      biliLoginBtn.classList.remove('logged-in');
    }
  } catch (e) {
    // 静默失败
  }
}

biliLoginBtn.addEventListener('click', () => {
  biliLoginModal.classList.remove('hidden');
  // 自动检查一次状态
  checkBiliLoginStatus();
  // 自动生成二维码
  generateBiliQrcode();
});

function closeBiliLoginModal() {
  biliLoginModal.classList.add('hidden');
  if (biliPollTimer) {
    clearInterval(biliPollTimer);
    biliPollTimer = null;
  }
}

biliGenerateBtn.addEventListener('click', generateBiliQrcode);

async function generateBiliQrcode() {
  biliLoginStatus.textContent = '正在生成二维码...';
  biliLoginStatus.className = 'bili-login-status loading';
  biliQrcodeArea.innerHTML = '<div class="bili-qrcode-placeholder">正在生成...</div>';

  // 清除旧的轮询
  if (biliPollTimer) {
    clearInterval(biliPollTimer);
    biliPollTimer = null;
  }

  try {
    const result = await api('/api/bili/login/qrcode');
    if (result.error) {
      biliLoginStatus.textContent = '生成失败: ' + result.error;
      biliLoginStatus.className = 'bili-login-status error';
      return;
    }

    // 使用后端返回的 base64 二维码图片
    if (result.qrcode_image) {
      biliQrcodeArea.innerHTML = `<img src="${result.qrcode_image}" alt="二维码" style="width:220px;height:220px;border-radius:12px;background:#fff;padding:8px;" />`;
    } else {
      biliQrcodeArea.innerHTML = '<div class="bili-qrcode-placeholder">二维码生成失败，请重试</div>';
      biliLoginStatus.textContent = '二维码图片生成失败';
      biliLoginStatus.className = 'bili-login-status error';
      return;
    }

    biliLoginStatus.textContent = '请用手机B站App扫描二维码';
    biliLoginStatus.className = 'bili-login-status';

    // 开始轮询
    startBiliPolling(result.qrcode_key);
  } catch (e) {
    biliLoginStatus.textContent = '生成失败: ' + e.message;
    biliLoginStatus.className = 'bili-login-status error';
  }
}

function startBiliPolling(qrcodeKey) {
  if (biliPollTimer) clearInterval(biliPollTimer);

  biliPollTimer = setInterval(async () => {
    try {
      const result = await api(`/api/bili/login/poll?qrcode_key=${encodeURIComponent(qrcodeKey)}`);

      if (result.status === 'waiting') {
        // 继续等待
      } else if (result.status === 'scanned') {
        biliLoginStatus.textContent = result.message;
        biliLoginStatus.className = 'bili-login-status scanned';
      } else if (result.status === 'success') {
        biliLoginStatus.textContent = result.message;
        biliLoginStatus.className = 'bili-login-status success';
        clearInterval(biliPollTimer);
        biliPollTimer = null;
        // 更新按钮状态
        checkBiliLoginStatus();
        // 1.5秒后关闭弹窗并刷新页面
        setTimeout(() => {
          closeBiliLoginModal();
          window.location.reload();
        }, 1500);
      } else if (result.status === 'expired') {
        biliLoginStatus.textContent = result.message;
        biliLoginStatus.className = 'bili-login-status error';
        clearInterval(biliPollTimer);
        biliPollTimer = null;
      } else if (result.status === 'error') {
        biliLoginStatus.textContent = result.message;
        biliLoginStatus.className = 'bili-login-status error';
        clearInterval(biliPollTimer);
        biliPollTimer = null;
      }
    } catch (e) {
      // 网络错误，继续轮询
    }
  }, 2000);
}
