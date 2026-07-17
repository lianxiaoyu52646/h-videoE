/**
 * 学习侧边栏 — 双语字幕同步 + 点词收藏
 */
class LearningPanel {
  constructor({ platform, videoId, videoTitle, videoUrl, getVideoEl, loadCaptions }) {
    this.platform = platform;
    this.videoId = videoId;
    this.videoTitle = videoTitle;
    this.videoUrl = videoUrl;
    this.getVideoEl = getVideoEl;
    this.loadCaptions = loadCaptions;
    this.captions = [];
    this.savedWords = new Set();
    this.activeIdx = -1;
    this.syncTimer = null;
    this.open = true;
    this.translating = false;
  }

  async init() {
    this.injectUI();
    this.bindToggle();
    await this.refreshSavedWords();
    await this.loadAndRenderCaptions();
    this.startSync();
    this.observeNavigation();
  }

  injectUI() {
    if (document.getElementById('ve-root')) return;

    const root = document.createElement('div');
    root.id = 've-root';
    root.innerHTML = `
      <button id="ve-toggle" title="VideoEnglish">学</button>
      <aside id="ve-panel" class="ve-open">
        <header class="ve-header">
          <div class="ve-title">VideoEnglish</div>
          <div class="ve-subtitle">${this.escape(this.videoTitle || '当前视频')}</div>
          <div class="ve-stats">
            <span id="ve-count">0 条字幕</span>
            <span id="ve-saved">0 个生词</span>
          </div>
        </header>
        <div id="ve-status" class="ve-status">加载字幕中...</div>
        <div id="ve-list" class="ve-list"></div>
        <footer class="ve-footer">
          <a id="ve-review-link" href="http://127.0.0.1:8000/vocab" target="_blank">打开复习页 →</a>
        </footer>
      </aside>
      <div id="ve-popup" class="ve-popup hidden"></div>
    `;
    document.body.appendChild(root);

    VideoEnglishAPI.getBase().then((base) => {
      const link = document.getElementById('ve-review-link');
      if (link) link.href = `${base}/vocab?video=${encodeURIComponent(this.videoId)}`;
    });
  }

  bindToggle() {
    document.getElementById('ve-toggle').addEventListener('click', () => {
      this.open = !this.open;
      document.getElementById('ve-panel').classList.toggle('ve-open', this.open);
    });
  }

  setStatus(msg, type = '') {
    const el = document.getElementById('ve-status');
    if (el) {
      el.textContent = msg;
      el.className = 've-status' + (type ? ` ve-${type}` : '');
    }
  }

  async refreshSavedWords() {
    try {
      const items = await VideoEnglishAPI.listSavedWords(this.videoId);
      this.savedWords = new Set(items.map((i) => i.word.toLowerCase()));
      const savedEl = document.getElementById('ve-saved');
      if (savedEl) savedEl.textContent = `${this.savedWords.size} 个生词`;
    } catch {
      this.setStatus('无法连接后端，请先启动 uvicorn', 'error');
    }
  }

  async loadAndRenderCaptions() {
    try {
      this.captions = await this.loadCaptions();
      if (!this.captions.length) {
        this.setStatus('未找到英文字幕，请在播放器中开启 CC 字幕', 'warn');
        return;
      }
      document.getElementById('ve-count').textContent = `${this.captions.length} 条字幕`;
      this.setStatus('正在翻译...');
      await this.translateCaptions();
      this.renderCaptions();
      this.setStatus('');
    } catch (e) {
      this.setStatus(`字幕加载失败: ${e.message}`, 'error');
    }
  }

  async translateCaptions() {
    if (this.translating) return;
    this.translating = true;
    const BATCH = 40;
    for (let i = 0; i < this.captions.length; i += BATCH) {
      const batch = this.captions.slice(i, i + BATCH);
      const need = batch.filter((c) => !c.translation && c.text);
      if (!need.length) continue;
      try {
        const { translations } = await VideoEnglishAPI.translateBatch(need.map((c) => c.text));
        need.forEach((c, j) => {
          c.translation = translations[j] || '';
        });
        if (i === 0) this.renderCaptions();
      } catch {
        break;
      }
    }
    this.translating = false;
  }

  renderCaptions() {
    const list = document.getElementById('ve-list');
    if (!list) return;
    list.innerHTML = '';
    this.captions.forEach((cap, idx) => {
      const row = document.createElement('div');
      row.className = 've-cue';
      row.dataset.idx = idx;
      row.innerHTML = `
        <div class="ve-cue-time">${this.formatTime(cap.start)}</div>
        <div class="ve-cue-en">${this.renderWords(cap.text, idx)}</div>
        <div class="ve-cue-zh">${this.escape(cap.translation || '')}</div>
      `;
      row.addEventListener('click', (e) => {
        if (e.target.closest('.ve-word')) return;
        this.seekTo(cap.start);
      });
      list.appendChild(row);
    });
    this.bindWordClicks();
  }

  renderWords(text, cueIdx) {
    const parts = text.split(/(\s+|[.,!?;:'"()\-—]+)/);
    return parts.map((part) => {
      if (!part || /^\s+$/.test(part) || /^[.,!?;:'"()\-—]+$/.test(part)) {
        return this.escape(part);
      }
      const clean = part.replace(/[^a-zA-Z'-]/g, '').toLowerCase();
      const saved = clean && this.savedWords.has(clean);
      return `<span class="ve-word${saved ? ' ve-saved' : ''}" data-word="${this.escape(clean)}" data-idx="${cueIdx}">${this.escape(part)}</span>`;
    }).join('');
  }

  bindWordClicks() {
    document.querySelectorAll('.ve-word').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const word = el.dataset.word;
        const idx = parseInt(el.dataset.idx, 10);
        if (word && word.length > 1) this.showWordPopup(word, idx, el);
      });
    });
  }

  async showWordPopup(word, cueIdx, anchorEl) {
    const cap = this.captions[cueIdx];
    const popup = document.getElementById('ve-popup');
    popup.classList.remove('hidden');
    popup.innerHTML = `<div class="ve-popup-loading">查询中...</div>`;

    const rect = anchorEl.getBoundingClientRect();
    popup.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - 220)}px`;
    popup.style.left = `${Math.min(rect.left, window.innerWidth - 300)}px`;

    try {
      const info = await VideoEnglishAPI.lookupWord(word);
      const saved = this.savedWords.has(word.toLowerCase());
      popup.innerHTML = `
        <button class="ve-popup-close">✕</button>
        <div class="ve-popup-word">${this.escape(info.word || word)}</div>
        <div class="ve-popup-phonetic">${this.escape(info.pronunciation || '')}</div>
        <div class="ve-popup-def">${this.escape(info.definition || '')}</div>
        <div class="ve-popup-zh">${this.escape(info.translation || info.youdao_translation || '')}</div>
        <div class="ve-popup-context">"${this.escape(cap?.text || '')}"</div>
        <button class="ve-popup-save ${saved ? 'saved' : ''}" ${saved ? 'disabled' : ''}>
          ${saved ? '★ 已收藏' : '★ 收藏生词'}
        </button>
      `;
      popup.querySelector('.ve-popup-close').onclick = () => popup.classList.add('hidden');
      popup.querySelector('.ve-popup-save')?.addEventListener('click', async () => {
        await this.saveWord(word, cueIdx, info);
        popup.classList.add('hidden');
      });
    } catch (e) {
      popup.innerHTML = `<div class="ve-popup-error">${this.escape(e.message)}</div>`;
    }
  }

  async saveWord(word, cueIdx, info) {
    const cap = this.captions[cueIdx];
    const video = this.getVideoEl();
    await VideoEnglishAPI.saveWord({
      word,
      source_platform: this.platform,
      source_video_id: this.videoId,
      source_url: this.videoUrl,
      source_title: this.videoTitle,
      sentence: cap?.text || '',
      sentence_translation: cap?.translation || '',
      timestamp: video?.currentTime ?? cap?.start ?? 0,
      definition: info.definition,
      pronunciation: info.pronunciation,
      part_of_speech: info.part_of_speech,
      translation: info.translation,
    });
    this.savedWords.add(word.toLowerCase());
    document.getElementById('ve-saved').textContent = `${this.savedWords.size} 个生词`;
    this.renderCaptions();
    this.highlightActive(this.activeIdx);
  }

  startSync() {
    if (this.syncTimer) clearInterval(this.syncTimer);
    this.syncTimer = setInterval(() => this.tick(), 120);
  }

  tick() {
    const video = this.getVideoEl();
    if (!video || !this.captions.length) return;
    const t = video.currentTime;
    let idx = -1;
    for (let i = 0; i < this.captions.length; i++) {
      const c = this.captions[i];
      if (t >= c.start && t < c.end) { idx = i; break; }
    }
    if (idx === -1) {
      for (let i = this.captions.length - 1; i >= 0; i--) {
        if (t >= this.captions[i].start) { idx = i; break; }
      }
    }
    if (idx !== this.activeIdx) {
      this.activeIdx = idx;
      this.highlightActive(idx);
    }
  }

  highlightActive(idx) {
    document.querySelectorAll('.ve-cue').forEach((el, i) => {
      el.classList.toggle('ve-active', i === idx);
    });
    const active = document.querySelector(`.ve-cue[data-idx="${idx}"]`);
    if (active) {
      active.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }

  seekTo(time) {
    const video = this.getVideoEl();
    if (video) {
      video.currentTime = time;
      if (video.paused) video.play().catch(() => {});
    }
  }

  observeNavigation() {
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        location.reload();
      }
    }, 1000);
  }

  formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  escape(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}
