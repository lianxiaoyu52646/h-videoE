// ── 生词本 + FSRS 复习（支持视频语境） ──
const vocabGrid = document.getElementById('vocabGrid');
const reviewArea = document.getElementById('reviewArea');
const vocabStats = document.getElementById('vocabStats');
const videoFilter = document.getElementById('videoFilter');

let reviewQueue = [];
let reviewIdx = 0;
let showAnswer = false;
let currentFilter = '';

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

function getFilterParam() {
  return currentFilter ? `?source_video_id=${encodeURIComponent(currentFilter)}` : '';
}

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatTime(sec) {
  if (sec == null) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function sourceIcon(platform) {
  if (platform === 'wordbook') return '📚';
  if (platform === 'reading') return '📖';
  if (platform === 'web') return '🌐';
  if (platform === 'bilibili') return '📺';
  if (platform === 'youtube') return '▶';
  return '📚';
}

function sourceLabel(v) {
  const icon = sourceIcon(v.source_platform);
  const title = v.source_title || v.source_video_id;
  return `${icon} ${title} (${v.word_count}词)`;
}

function jumpLabel(card) {
  if (card.source_platform === 'reading') return '回到阅读 →';
  if (card.source_platform === 'wordbook') return '回到词书 →';
  return '回到视频 →';
}

function videoJumpUrl(card) {
  if (card.source_platform === 'wordbook') {
    const id = card.wordbook_id || (card.source_video_id || '').replace('wordbook-', '');
    return id ? `/wordbook?id=${id}` : '/wordbooks';
  }
  if (card.source_platform === 'reading') {
    const id = (card.source_video_id || '').replace('reading-', '');
    return card.source_url || (id ? `/reader?id=${id}` : null);
  }
  if (card.source_platform === 'web') {
    return card.source_url || null;
  }
  if (!card.source_url) return null;
  const sep = card.source_url.includes('?') ? '&' : '?';
  if (card.source_platform === 'youtube' && card.timestamp != null) {
    return `${card.source_url}${sep}t=${Math.floor(card.timestamp)}`;
  }
  if (card.source_platform === 'bilibili' && card.timestamp != null) {
    return `${card.source_url}${sep}t=${Math.floor(card.timestamp)}`;
  }
  return card.source_url;
}

function dueStatus(card) {
  const due = new Date(card.due).getTime();
  const now = Date.now();
  if (due <= now) return { text: '需复习', cls: 'now' };
  const diff = due - now;
  if (diff < 86400000) return { text: '即将到期', cls: 'soon' };
  return { text: `${Math.ceil(diff / 86400000)} 天后`, cls: 'later' };
}

async function loadVideoFilter() {
  try {
    const videos = await api('/api/vocab/videos');
    const params = new URLSearchParams(location.search);
    const preselect = params.get('video') || '';
    videoFilter.innerHTML = '<option value="">全部来源</option>';
    videos.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.source_video_id;
      opt.textContent = sourceLabel(v);
      videoFilter.appendChild(opt);
    });
    if (preselect) {
      videoFilter.value = preselect;
      currentFilter = preselect;
    }
  } catch (_) {}
}

videoFilter.addEventListener('change', async () => {
  currentFilter = videoFilter.value;
  reviewIdx = 0;
  showAnswer = false;
  await loadVocab();
  await loadRecommendations();
});

async function loadVocab() {
  try {
    const items = await api(`/api/vocab${getFilterParam()}`);
    renderVocab(items);
    renderStats(items);
  } catch (e) {
    vocabGrid.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function renderStats(items) {
  const dueCount = items.filter(i => new Date(i.due).getTime() <= Date.now()).length;
  const practiceLink = currentFilter
    ? `<a class="vocab-practice-link" href="/vocab?video=${encodeURIComponent(currentFilter)}#practiceSection">去练习 ↓</a>`
    : '';
  vocabStats.innerHTML = `
    <span>总计: ${items.length}</span>
    <span>需复习: ${dueCount}</span>
    <span>已掌握: ${items.filter(i => i.reps >= 3).length}</span>
    ${practiceLink}
  `;
}

function renderVocab(items) {
  if (!items.length) {
    vocabGrid.innerHTML = `<div class="empty-state"><h3>还没有生词</h3><p>在视频学习、英文阅读或词书页面把单词加入学习吧！</p></div>`;
    return;
  }
  vocabGrid.innerHTML = '';
  items.forEach(card => {
    const ds = dueStatus(card);
    const jump = videoJumpUrl(card);
    const div = document.createElement('div');
    div.className = 'vocab-card';
    div.innerHTML = `
      <div class="word-header">
        <span class="word-title">${escapeHtml(card.word)}</span>
        <button class="btn-danger" data-id="${card.id}">已学会</button>
      </div>
      <div class="word-phonetic">${escapeHtml(card.pronunciation || '')}</div>
      <div class="word-def">${escapeHtml(card.definition || '')}</div>
      ${card.sentence ? `<div class="word-context">"${escapeHtml(card.sentence)}"</div>` : ''}
      ${card.source_title ? `<div class="word-source">${sourceIcon(card.source_platform)} ${escapeHtml(card.source_title)}${card.timestamp != null ? ' · ' + formatTime(card.timestamp) : ''}</div>` : ''}
      ${jump ? `<a class="word-jump" href="${escapeHtml(jump)}">${jumpLabel(card)}</a>` : ''}
      <div class="word-meta">
        <span>复习 ${card.reps} 次</span>
        <span class="due-badge ${ds.cls}">${ds.text}</span>
      </div>
    `;
    div.querySelector('.btn-danger').addEventListener('click', async () => {
      await api(`/api/vocab/${card.id}`, { method: 'DELETE' });
      await loadVocab();
      await loadRecommendations();
    });
    vocabGrid.appendChild(div);
  });
}

async function loadRecommendations() {
  try {
    reviewQueue = await api(`/api/recommendations${getFilterParam()}`);
    reviewIdx = 0;
    showAnswer = false;
    renderReview();
  } catch (e) {
    reviewArea.innerHTML = `<p style="color:var(--muted)">暂无推荐</p>`;
  }
}

function speakWord(word) {
  const w = String(word || '').trim();
  if (!w) return;
  try {
    if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
      window.AndroidDictionary.speak(w);
      return;
    }
  } catch (_) { /* fall through */ }
  if ('speechSynthesis' in window) {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(w);
    u.lang = 'en-US';
    u.rate = 0.85;
    speechSynthesis.speak(u);
  }
}

function renderReview() {
  if (reviewIdx >= reviewQueue.length) {
    reviewArea.innerHTML = `
      <div class="empty-state">
        <h3>🎉 全部复习完成！</h3>
        <p>暂时没有需要复习的单词了。去看新视频收藏更多生词吧。</p>
      </div>
    `;
    return;
  }
  const card = reviewQueue[reviewIdx];
  const jump = videoJumpUrl(card);
  const progress = `${reviewIdx + 1} / ${reviewQueue.length}`;

  if (!showAnswer) {
    reviewArea.innerHTML = `
      <div class="review-card">
        <div class="review-progress">${progress}</div>
      ${card.sentence ? `<div class="review-context">"${escapeHtml(card.sentence)}"</div>` : ''}
      ${card.sentence_translation ? `<div class="review-context-zh">${escapeHtml(card.sentence_translation)}</div>` : ''}
        <p class="review-hint">看句子猜词义，想好了再显示答案</p>
        <button id="showAnswerBtn" class="btn-primary">显示答案</button>
        ${jump ? `<a class="word-jump" href="${jump}">${card.source_platform === 'reading' ? '📖 回到阅读' : card.source_platform === 'wordbook' ? '📚 回到词书' : '📺 回到原视频'}</a>` : ''}
      </div>
    `;
    document.getElementById('showAnswerBtn').addEventListener('click', () => {
      showAnswer = true;
      renderReview();
      speakWord(card.word);
    });
    return;
  }

  reviewArea.innerHTML = `
    <div class="review-card">
      <div class="review-progress">${progress}</div>
      <div class="word-big" style="display:flex;align-items:center;justify-content:center;gap:12px;">
        <span>${escapeHtml(card.word)}</span>
        <button type="button" class="tts-btn" id="speakReviewWord" aria-label="朗读" title="朗读">🔊</button>
      </div>
      <div class="word-phonetic-big">${escapeHtml(card.pronunciation || '')}</div>
      <div class="word-def-big">${escapeHtml(card.definition || '')}</div>
      ${card.translation ? `<div class="word-def-big" style="color:var(--accent)">${escapeHtml(card.translation)}</div>` : ''}
      <div class="review-buttons">
        <button class="review-btn good" data-rating="4">会</button>
        <button class="review-btn again" data-rating="1">不会</button>
      </div>
    </div>
  `;
  document.getElementById('speakReviewWord')?.addEventListener('click', () => speakWord(card.word));
  reviewArea.querySelectorAll('.review-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const rating = parseInt(btn.dataset.rating);
      await api('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vocab_id: card.id, rating }),
      });
      reviewIdx++;
      showAnswer = false;
      renderReview();
      await loadVocab();
    });
  });
}

window.addEventListener('load', async () => {
  await loadVideoFilter();
  await loadVocab();
  await loadRecommendations();
});
