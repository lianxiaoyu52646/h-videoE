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
    },
  };

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

  /** Real-time English TTS: Android bridge first, else Web Speech API. */
  function speakWord(word) {
    const w = String(word || '').trim();
    if (!w) return;
    try {
      if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
        window.AndroidDictionary.speak(w);
        return;
      }
    } catch (_) { /* fall through */ }
    if (!('speechSynthesis' in window)) {
      toast('当前环境不支持朗读');
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(w);
      u.lang = 'en-US';
      u.rate = 0.9;
      window.speechSynthesis.speak(u);
    } catch (_) {
      toast('朗读失败');
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
    state.tab = tab;
    $$('#tabNav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${tab}`));
    if (tab === 'read') renderRead();
    if (tab === 'books') renderBooks();
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
      resumeTarget: 0,
      observers: [],
      onScroll: null,
      cursorTimer: null,
      lastSavedCursor: null,
      bootstrapped: false,
      feedSeq: 0,
    };
    await loadStudyPage('resume');
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
          await refreshVocab();
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
        : (s.hasMoreBefore ? '↑ 继续上滑 · 回到更早的词' : '▲ 词书开头（第 1 个词）');
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
    wrap.innerHTML = items.map((it) => studyRowHtml(it, { animate: true })).join('');
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

  function applyStudyPage(data, mode) {
    const s = state.study;
    if (!s) return [];
    const items = data.items || [];
    const pageOffset = Number(data.offset ?? 0);
    const pageLimit = Math.max(1, Number(data.limit ?? 20));
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
      if (s.loadingBefore || !s.hasMoreBefore) return;
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
    const pageSize = 20;
    (s.observers || []).forEach((io) => io.disconnect());
    s.observers = [];
    updateStudySentinels();

    try {
      let url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}`;
      if (mode === 'after') {
        url += `&offset=${s.nextOffset}`;
      } else if (mode === 'before') {
        const limit = Math.min(pageSize, s.startOffset);
        const offset = Math.max(0, s.startOffset - limit);
        url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${limit}&offset=${offset}`;
      }
      // resume: omit offset → server opens at saved cursor; list stays ordered 0..N-1
      const data = await api(url);
      if (state.study !== s || seq !== s.feedSeq) return;

      const fresh = applyStudyPage(data, mode === 'resume' ? 'resume' : mode);

      if (mode === 'resume' || !s.bootstrapped) {
        s.bootstrapped = true;
        renderBooks();
        return;
      }

      if (mode === 'after') appendStudyRows(fresh);
      else if (mode === 'before') prependStudyRows(fresh);
      updateStudyProgressUi();
      updateStudySentinels();
    } catch (e) {
      toast(e.message);
    } finally {
      if (state.study === s) {
        if (mode === 'before') s.loadingBefore = false;
        else s.loadingAfter = false;
        updateStudySentinels();
        if (mode !== 'resume' && s.bootstrapped) {
          setTimeout(() => {
            if (state.study === s) attachStudyObservers();
          }, 100);
        }
      }
    }
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
    s.cursorTimer = setTimeout(() => saveStudyCursor(false), 450);
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
      const io = new IntersectionObserver((entries) => {
        if (!entries.some((en) => en.isIntersecting)) return;
        loadStudyPage(mode);
      }, { rootMargin: mode === 'after' ? '80px' : '40px', threshold: 0 });
      io.observe(el);
      s.observers.push(io);
    };

    if (s.hasMoreBefore) watch($('#studySentinelTop'), 'before');
    if (s.hasMoreAfter) watch($('#studySentinelBottom'), 'after');

    s.onScroll = () => {
      syncActiveStudyRowFromScroll();
      scheduleSaveStudyCursor();
    };
    window.addEventListener('scroll', s.onScroll, { passive: true });
    syncActiveStudyRowFromScroll();
  }

  function scrollToResumeWord() {
    const s = state.study;
    if (!s) return;
    const target = s.resumeTarget;
    const row = $(`#studyList .study-row[data-offset="${target}"]`)
      || $('#studyList .study-row');
    if (!row) return;
    const y = row.getBoundingClientRect().top + window.scrollY - 88;
    window.scrollTo(0, Math.max(0, y));
    setActiveStudyRow(Number(row.dataset.offset ?? target));
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
        s.hasMoreBefore ? '↑ 继续上滑 · 回到更早的词' : '▲ 词书开头（第 1 个词）'
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
      teardownStudyObservers();
      state.study = null;
      await loadBooks();
      renderBooks();
    };

    bindStudyStarButtons(root);
    if (s.resumeTarget != null) setActiveStudyRow(s.resumeTarget);

    requestAnimationFrame(() => {
      scrollToResumeWord();
      attachStudyObservers();
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
    root.innerHTML = `
      <div class="m-hero">
        <h1>生词本 · 每日练习</h1>
        <p>FSRS 智能推送。点「会」移出；点「不会」继续练。</p>
      </div>
      <div class="m-card">
        <h2>今日练习 ${due.length ? `(${due.length})` : ''}</h2>
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
        ` : '<p class="m-muted">今天没有到期词，去阅读或词书收集一些吧</p>'}
      </div>
      <div class="m-card">
        <h2>全部生词 (${(state.vocab || []).length})</h2>
        ${(state.vocab || []).map((v) => `
          <div class="m-list-item">
            <span>
              <strong>${escapeHtml(v.word)}</strong>
              <span class="m-muted">${escapeHtml(v.pronunciation || '')}</span>
              <span class="m-muted">${escapeHtml(v.translation || v.definition || '')}</span>
            </span>
            <span class="m-list-actions">
              ${speakBtnHtml(v.word, 'speak-btn-sm')}
              <button class="m-btn m-btn-mint" data-know="${v.id}" type="button">会</button>
            </span>
          </div>`).join('') || '<p class="m-muted">生词本是空的</p>'}
      </div>`;

    $('#reviewKnow')?.addEventListener('click', () => reviewOrRemove(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewOrRemove(false));
    $$('[data-know]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          await api(`/api/vocab/${btn.dataset.know}`, { method: 'DELETE' });
          await loadVocab();
          toast('已移出生词本');
          renderVocab();
        } catch (e) { toast(e.message); }
      });
    });
  }

  async function reviewOrRemove(know) {
    const card = (state.due || [])[0];
    if (!card) return;
    try {
      if (know) {
        await api('/api/review', { method: 'POST', body: { vocab_id: card.id, rating: 4 } });
        await api(`/api/vocab/${card.id}`, { method: 'DELETE' });
        toast('会！已移出');
      } else {
        await api('/api/review', { method: 'POST', body: { vocab_id: card.id, rating: 1 } });
        toast('不会，稍后再练');
      }
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
            <option value="">随机词典</option>
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
    state.bookTranslate.progress = data.progress || null;
    state.bookTranslate.checkpoint = data.checkpoint || data.progress?.checkpoint || null;
    state.bookTranslate.resumable = !!data.resumable;
    state.bookTranslate.running = !!data.running;
    if (data.running) startBookTranslatePoll();
    else stopBookTranslatePoll();
    if (state.tab === 'mine') renderMine();
    return data;
  }

  async function startBookTranslateJob() {
    const bt = state.bookTranslate;
    if (bt.running || bt.loading) return;
    const pending = Number(bt.scan?.pending_books || 0);
    if (!pending && !bt.resumable) {
      toast('没有待译书籍');
      return;
    }
    bt.loading = true;
    renderMine();
    try {
      await api(
        `/api/jobs/book-translate/backfill?full_run=true&ensure_catalog=true&batch_size=20&max_books=${Math.min(100, Math.max(pending, 1))}`,
        { method: 'POST' },
      );
      toast(bt.resumable ? '从断点继续翻译' : `开始翻译 ${pending} 本书`);
      await refreshBookTranslateStatus({ ensureCatalog: false });
      startBookTranslatePoll();
    } catch (e) {
      toast(e.message || '启动失败');
    } finally {
      bt.loading = false;
      if (state.tab === 'mine') renderMine();
    }
  }

  function renderMine() {
    const u = state.user || {};
    const bt = state.bookTranslate;
    const scan = bt.scan || {};
    const prog = bt.progress || {};
    const cp = bt.checkpoint || {};
    const pending = Number(scan.pending_books || 0);
    const doneBooks = Number(scan.done_books || 0);
    const totalBooks = Number(scan.total_books || 0);
    const running = !!bt.running;
    const resumable = !!bt.resumable && !running;
    const percent = running
      ? Math.max(0, Math.min(100, Number(prog.percent || cp.percent || 0)))
      : (cp.books_total
        ? Math.max(0, Math.min(100, Number(cp.percent || 0)))
        : (totalBooks ? Math.round((doneBooks / totalBooks) * 100) : 0));
    const statusLine = running
      ? (prog.message || `翻译中 ${prog.books_finished || 0}/${prog.books_total || pending}`)
      : (resumable
        ? (cp.message || `可从断点继续（已完成 ${cp.books_finished || 0}/${cp.books_total || pending} 本）`)
        : (pending ? `发现 ${pending} 本尚未译完` : (totalBooks ? '全部书籍已翻译完成' : '点击下方扫描经典书架')));
    const current = (running || resumable) && (prog.current_title || cp.current_book_key)
      ? `<div class="m-muted" style="margin-top:6px;">断点：${escapeHtml(prog.current_title || cp.current_book_key || '')}${cp.current_order_index ? ` · 段 ${cp.current_order_index}` : ''}</div>`
      : '';
    const cta = running ? '翻译进行中…' : (bt.loading ? '启动中…' : (resumable ? '继续翻译' : '开始自动翻译'));

    $('#view-mine').innerHTML = `
      <div class="m-hero"><h1>我的</h1><p>账号与阅读偏好</p></div>
      <div class="m-card">
        <div style="display:flex;align-items:center;gap:14px;">
          <div class="m-logo" style="width:56px;height:56px;font-size:1.6rem;border-radius:20px;">🫧</div>
          <div>
            <h2 style="margin:0;">${escapeHtml(u.username || '学员')}</h2>
            <p class="m-muted" style="margin:4px 0 0;">已登录 · 单词泡泡学员</p>
          </div>
        </div>
      </div>
      <div class="m-card book-translate-card">
        <h2 style="margin:0 0 6px;">经典书库翻译</h2>
        <p class="m-muted" style="margin:0;">人工触发 · 断点续传 · 已译跳过</p>
        <div class="bt-stats">
          <span>待译 <strong>${pending}</strong></span>
          <span>已完成 <strong>${doneBooks}</strong></span>
          <span>共 <strong>${totalBooks}</strong></span>
        </div>
        <div class="progress-bar-wrap bt-progress"><div class="progress-bar" style="width:${percent}%"></div></div>
        <div class="bt-status">${escapeHtml(statusLine)}</div>
        ${current}
        <div class="bt-actions">
          <button class="m-btn m-btn-ghost" id="scanBooksBtn" type="button" ${running || bt.loading ? 'disabled' : ''}>扫描待译</button>
          <button class="m-btn m-btn-primary" id="startTranslateBtn" type="button" ${running || bt.loading || (!pending && !resumable) ? 'disabled' : ''}>
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
    $('#scanBooksBtn')?.addEventListener('click', async () => {
      try {
        toast('扫描中…');
        await refreshBookTranslateStatus({ ensureCatalog: true });
        toast(`待译 ${state.bookTranslate.scan?.pending_books || 0} 本`);
      } catch (e) { toast(e.message); }
    });
    $('#startTranslateBtn')?.addEventListener('click', () => startBookTranslateJob());
  }

  $('#userBtn').addEventListener('click', () => setTab('mine'));
  $$('#tabNav button').forEach((btn) => btn.addEventListener('click', () => setTab(btn.dataset.tab)));

  // Capture phase so speak works even inside PK option buttons.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-speak-word]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    speakWord(btn.dataset.speakWord);
  }, true);

  async function boot() {
    applyEyecare();
    if (!(await ensureAuth())) return;
    try {
      await Promise.all([loadReadings(), loadBooks(), loadVocab()]);
    } catch (e) { console.warn(e); }
    refreshBookTranslateStatus({ ensureCatalog: false }).catch(() => {});
    setTab('read');
  }
  boot();
})();
