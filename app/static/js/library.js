// 视频库首页
const loadBtn = document.getElementById('loadBtn');
const videoUrlInput = document.getElementById('videoUrl');
const videoList = document.getElementById('videoList');
const videoListCount = document.getElementById('videoListCount');
const statusMsg = document.getElementById('statusMsg');

let pollTimer = null;

const LEARNABLE = new Set(['ready', 'translating', 'done']);
const BUSY = new Set(['pending', 'processing', 'translating']);

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

function showStatus(msg, type = '') {
  statusMsg.textContent = msg;
  statusMsg.className = 'status-msg ' + type;
}

function statusLabel(v) {
  const map = {
    metadataReady: '准备中',
    subtitleReady: '字幕就绪',
    translationStreaming: '补译中',
    reviewReady: '可复习',
    failed: '无字幕',
  };
  return map[v.learn_phase] || map.metadataReady;
}

function statusClass(v) {
  if (v.learn_phase === 'reviewReady') return 'done';
  if (v.learn_phase === 'failed') return 'failed';
  if (v.learn_phase === 'subtitleReady' || v.learn_phase === 'translationStreaming') return 'processing';
  return 'pending';
}

function canLearn(v) {
  return LEARNABLE.has(v.subtitle_status) && v.subtitle_count > 0;
}

function formatDuration(sec) {
  if (!sec) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h${m}m` : `${m}m`;
}

function renderList(videos) {
  videoListCount.textContent = videos.length;
  if (!videos.length) {
    videoList.innerHTML = '<div class="empty-state"><p>还没有视频，粘贴链接添加吧</p></div>';
    return;
  }
  videoList.innerHTML = '';
  videos.forEach(v => {
    const learn = canLearn(v);
    const tooLongForWhisper = (v.duration_seconds || 0) > 600;
    const card = document.createElement('div');
    card.className = 'video-list-item';
    card.innerHTML = `
      <div class="vli-main">
        <div class="vli-title">${escapeHtml(v.title || v.url)}</div>
        <div class="vli-meta">
          <span>${v.source}</span>
          <span>${formatDuration(v.duration_seconds)}</span>
          <span>${v.subtitle_count} 条字幕</span>
        </div>
        ${v.status_message ? `<div class="vli-msg">${escapeHtml(v.status_message)}</div>` : ''}
        ${BUSY.has(v.subtitle_status) ? `
          <div class="vli-progress"><div class="vli-progress-bar" style="width:${v.progress}%"></div></div>
          <div class="vli-pct">${v.progress}%</div>
        ` : ''}
      </div>
      <div class="vli-actions">
        <span class="status-badge ${statusClass(v)}">${statusLabel(v)}</span>
        ${learn ? `<a class="btn-primary" href="/learn?id=${v.id}">开始学习</a>` : `<a class="btn-secondary" href="/learn?id=${v.id}">查看详情</a>`}
        ${v.subtitle_status === 'failed' ? `
          <button class="btn-secondary" data-retry="${v.id}">重试</button>
          ${tooLongForWhisper
            ? `<span class="vli-tip">超长视频不建议整段识别</span>`
            : `<button class="btn-secondary" data-whisper="${v.id}" title="仅建议10分钟以内短视频">语音识别</button>`}
        ` : ''}
      </div>
    `;
    card.querySelector('[data-retry]')?.addEventListener('click', async (e) => {
      await api(`/api/videos/${e.target.dataset.retry}/refetch`, { method: 'POST' });
      refreshList();
    });
    card.querySelector('[data-whisper]')?.addEventListener('click', async (e) => {
      if (!confirm('语音识别很慢，仅建议 10 分钟以内的短视频。确定继续？')) return;
      await api(`/api/videos/${e.target.dataset.whisper}/whisper`, { method: 'POST' });
      refreshList();
    });
    videoList.appendChild(card);
  });
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function refreshList() {
  try {
    const videos = await api('/api/videos');
    renderList(videos);
    const busy = videos.some(v => BUSY.has(v.subtitle_status));
    if (busy && !pollTimer) {
      pollTimer = setInterval(refreshList, 3000);
    } else if (!busy && pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  } catch (e) {
    videoList.innerHTML = `<div class="empty-state"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function addVideo() {
  const url = videoUrlInput.value.trim();
  if (!url) return;
  loadBtn.disabled = true;
  showStatus('正在获取字幕...', 'loading');
  try {
    await api('/api/videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    videoUrlInput.value = '';
    showStatus('已加入视频库', 'success');
    await refreshList();
  } catch (e) {
    showStatus('添加失败: ' + e.message, 'error');
  } finally {
    loadBtn.disabled = false;
  }
}

loadBtn.addEventListener('click', addVideo);
videoUrlInput.addEventListener('keypress', e => { if (e.key === 'Enter') addVideo(); });
refreshList();
