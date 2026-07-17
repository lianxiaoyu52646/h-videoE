/**
 * 网页阅读侧边栏 — 提取正文 + 双语 + 点词 + 保存书库
 */
class WebReadingPanel {
  constructor({ pageTitle, pageUrl, articleText }) {
    this.pageTitle = pageTitle;
    this.pageUrl = pageUrl;
    this.articleText = articleText;
    this.blocks = [];
    this.savedWords = new Set();
    this.docId = null;
    this.sourceId = `web-${btoa(pageUrl).slice(0, 24).replace(/[^a-zA-Z0-9]/g, '')}`;
    this.open = false;
  }

  async init() {
    this.splitBlocks();
    this.injectUI();
    this.bindToggle();
    await this.refreshSavedWords();
    await this.translateBlocks();
    this.renderBlocks();
  }

  splitBlocks() {
    const parts = this.articleText.split(/\n\s*\n+/).map((p) => p.trim()).filter(Boolean);
    if (parts.length <= 1 && this.articleText.includes('\n')) {
      this.blocks = this.articleText.split('\n').map((l) => l.trim()).filter(Boolean);
    } else {
      this.blocks = parts.length ? parts : [this.articleText];
    }
    this.blocks = this.blocks.map((text) => ({ text, translation: '' }));
  }

  injectUI() {
    if (document.getElementById('ve-read-root')) return;
    const root = document.createElement('div');
    root.id = 've-read-root';
    root.innerHTML = `
      <button id="ve-read-toggle" title="网页阅读">读</button>
      <aside id="ve-read-panel">
        <header class="ve-header">
          <div class="ve-title">📖 网页阅读</div>
          <div class="ve-subtitle">${this.escape(this.pageTitle)}</div>
          <div class="ve-stats">
            <span id="ve-read-count">${this.blocks.length} 段</span>
            <span id="ve-read-saved">0 生词</span>
          </div>
        </header>
        <div id="ve-read-status" class="ve-status"></div>
        <div class="ve-read-actions">
          <button id="ve-save-library" class="ve-btn-primary">💾 保存到书库</button>
          <a id="ve-open-reader" class="ve-btn-link hidden" target="_blank">完整阅读器 →</a>
        </div>
        <div id="ve-read-list" class="ve-list"></div>
        <footer class="ve-footer">
          <a id="ve-read-vocab" href="http://127.0.0.1:8000/vocab" target="_blank">生词本 →</a>
        </footer>
      </aside>
      <div id="ve-read-popup" class="ve-popup hidden"></div>
    `;
    document.body.appendChild(root);

    VideoEnglishAPI.getBase().then((base) => {
      const link = document.getElementById('ve-read-vocab');
      if (link) link.href = `${base}/vocab`;
    });

    document.getElementById('ve-save-library').addEventListener('click', () => this.saveToLibrary());
  }

  bindToggle() {
    document.getElementById('ve-read-toggle').addEventListener('click', () => {
      this.open = !this.open;
      document.getElementById('ve-read-panel').classList.toggle('ve-open', this.open);
    });
  }

  setStatus(msg, type = '') {
    const el = document.getElementById('ve-read-status');
    if (el) {
      el.textContent = msg;
      el.className = 've-status' + (type ? ` ve-${type}` : '');
    }
  }

  async refreshSavedWords() {
    try {
      const items = await VideoEnglishAPI.listSavedWords(this.sourceId);
      this.savedWords = new Set(items.map((i) => i.word.toLowerCase()));
      const el = document.getElementById('ve-read-saved');
      if (el) el.textContent = `${this.savedWords.size} 生词`;
    } catch {
      this.setStatus('无法连接后端', 'error');
    }
  }

  async translateBlocks() {
    this.setStatus('翻译中...');
    const BATCH = 30;
    for (let i = 0; i < this.blocks.length; i += BATCH) {
      const batch = this.blocks.slice(i, i + BATCH);
      const need = batch.filter((b) => !b.translation);
      if (!need.length) continue;
      try {
        const { translations } = await VideoEnglishAPI.translateBatch(need.map((b) => b.text));
        need.forEach((b, j) => { b.translation = translations[j] || ''; });
      } catch {
        break;
      }
    }
    this.setStatus('');
  }

  renderBlocks() {
    const list = document.getElementById('ve-read-list');
    if (!list) return;
    list.innerHTML = '';
    this.blocks.forEach((block, idx) => {
      const row = document.createElement('div');
      row.className = 've-cue';
      row.innerHTML = `
        <div class="ve-cue-en">${this.renderWords(block.text, idx)}</div>
        <div class="ve-cue-zh">${this.escape(block.translation || '')}</div>
      `;
      list.appendChild(row);
    });
    this.bindWordClicks();
  }

  renderWords(text, blockIdx) {
    return text.split(/(\s+)/).map((part) => {
      if (!part.trim()) return this.escape(part);
      const clean = part.replace(/[^a-zA-Z'-]/g, '').toLowerCase();
      if (!clean) return this.escape(part);
      const saved = this.savedWords.has(clean.split("'")[0]) ? ' ve-saved' : '';
      return `<span class="ve-word${saved}" data-word="${this.escape(clean)}" data-idx="${blockIdx}">${this.escape(part)}</span>`;
    }).join('');
  }

  bindWordClicks() {
    document.querySelectorAll('#ve-read-list .ve-word').forEach((el) => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        this.showWordPopup(el.dataset.word, parseInt(el.dataset.idx, 10), el);
      });
    });
  }

  async showWordPopup(word, blockIdx, anchorEl) {
    const block = this.blocks[blockIdx];
    const popup = document.getElementById('ve-read-popup');
    popup.classList.remove('hidden');
    popup.innerHTML = '<div class="ve-popup-loading">查询中...</div>';
    const rect = anchorEl.getBoundingClientRect();
    popup.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - 220)}px`;
    popup.style.left = `${Math.min(rect.left, window.innerWidth - 300)}px`;

    try {
      const info = await VideoEnglishAPI.lookupWord(word);
      const saved = this.savedWords.has(word.toLowerCase());
      popup.innerHTML = `
        <button class="ve-popup-close">✕</button>
        <div class="ve-popup-word">${this.escape(info.word || word)}</div>
        <div class="ve-popup-def">${this.escape(info.definition || '')}</div>
        <div class="ve-popup-zh">${this.escape(info.translation || '')}</div>
        <button class="ve-popup-save ${saved ? 'saved' : ''}" ${saved ? 'disabled' : ''}>
          ${saved ? '★ 已收藏' : '★ 收藏生词'}
        </button>
      `;
      popup.querySelector('.ve-popup-close').onclick = () => popup.classList.add('hidden');
      popup.querySelector('.ve-popup-save')?.addEventListener('click', async () => {
        await VideoEnglishAPI.saveWord({
          word,
          source_platform: 'web',
          source_video_id: this.sourceId,
          source_url: this.pageUrl,
          source_title: this.pageTitle,
          sentence: block?.text || '',
          sentence_translation: block?.translation || '',
          definition: info.definition,
          pronunciation: info.pronunciation,
          translation: info.translation,
        });
        this.savedWords.add(word.toLowerCase());
        document.getElementById('ve-read-saved').textContent = `${this.savedWords.size} 生词`;
        this.renderBlocks();
        popup.classList.add('hidden');
      });
    } catch (e) {
      popup.innerHTML = `<div class="ve-popup-error">${this.escape(e.message)}</div>`;
    }
  }

  async saveToLibrary() {
    this.setStatus('保存中...');
    try {
      const doc = await VideoEnglishAPI.createReading({
        title: this.pageTitle,
        content: this.blocks.map((b) => b.text).join('\n\n'),
        source_type: 'web',
        source_url: this.pageUrl,
      });
      this.docId = doc.id;
      const base = await VideoEnglishAPI.getBase();
      try {
        await VideoEnglishAPI.migrateVocab(doc.id, {
          from_source_id: this.sourceId,
          source_platform: 'reading',
          source_url: `${base}/reader?id=${doc.id}`,
          source_title: this.pageTitle,
        });
        this.sourceId = `reading-${doc.id}`;
        await this.refreshSavedWords();
      } catch (_) {}
      this.setStatus('已保存到书库', 'success');
      const link = document.getElementById('ve-open-reader');
      link.href = `${base}/reader?id=${doc.id}`;
      link.classList.remove('hidden');
    } catch (e) {
      this.setStatus('保存失败: ' + e.message, 'error');
    }
  }

  escape(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}
