const params = new URLSearchParams(location.search);
const wordbookId = parseInt(params.get('id') || '0', 10);
const DEFAULT_PAGE_SIZE = 10;
const ALLOWED_PAGE_SIZES = [10, 20, 50, 100];

const wordbookStatus = document.getElementById('wordbookStatus');
const entrySearchInput = document.getElementById('entrySearchInput');
const clearEntrySearchBtn = document.getElementById('clearEntrySearchBtn');
const pageSizeSelect = document.getElementById('pageSizeSelect');
const jumpPageInput = document.getElementById('jumpPageInput');
const jumpPageBtn = document.getElementById('jumpPageBtn');
const entriesList = document.getElementById('entriesList');
const pageStatus = document.getElementById('pageStatus');
const paginationContainer = document.getElementById('paginationContainer');
const onlySavedToggle = document.getElementById('onlySavedToggle');
const detailAddWordInput = document.getElementById('detailAddWordInput');
const detailAddWordBtn = document.getElementById('detailAddWordBtn');
const detailImportFileInput = document.getElementById('detailImportFileInput');
const detailWordPreview = document.getElementById('detailWordPreview');

let currentWordbook = null;
let currentPage = parsePositiveInt(params.get('page'), 1);
let currentPageSize = sanitizePageSize(params.get('page_size'));
let currentQuery = (params.get('q') || '').trim();
let onlySaved = params.get('saved') === '1';
let currentPageState = null;
let currentEntryMap = new Map();
let paginationInstance = null;
let searchTimer = null;
let starredWords = new Set();
let savingWords = new Set();
let detailPreviewTimer = null;
let detailPreviewRequestId = 0;

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || '请求失败');
  }
  return resp.json();
}

function parsePositiveInt(value, fallback = 1) {
  const parsed = parseInt(String(value || ''), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function sanitizePageSize(value) {
  const parsed = parsePositiveInt(value, DEFAULT_PAGE_SIZE);
  return ALLOWED_PAGE_SIZES.includes(parsed) ? parsed : DEFAULT_PAGE_SIZE;
}

function normalizeWord(value) {
  return String(value || '').trim().toLowerCase();
}

function setStatus(message, type = '') {
  wordbookStatus.textContent = message;
  wordbookStatus.className = `status-msg ${type}`.trim();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function syncUrl() {
  const next = new URLSearchParams();
  next.set('id', String(wordbookId));
  if (currentPage > 1) next.set('page', String(currentPage));
  if (currentPageSize !== DEFAULT_PAGE_SIZE) next.set('page_size', String(currentPageSize));
  if (currentQuery) next.set('q', currentQuery);
  if (onlySaved) next.set('saved', '1');
  history.replaceState({}, '', `/wordbook?${next.toString()}`);
}

function hasCjk(text) {
  return /[\u4e00-\u9fff]/.test(String(text || ''));
}

function formatEntryDisplay(entry) {
  const translation = String(entry.translation || '').trim();
  const definition = String(entry.definition || '').trim();

  if (translation && translation === definition) {
    if (hasCjk(translation)) {
      return { chinese: translation, english: '' };
    }
    return { chinese: '', english: translation };
  }

  let chinese = '';
  let english = '';
  if (hasCjk(translation)) chinese = translation;
  else if (hasCjk(definition)) chinese = definition;

  if (!hasCjk(translation) && translation) english = translation;
  if (!hasCjk(definition) && definition && definition !== english) english = definition;

  return {
    chinese,
    english: english && english !== chinese ? english : '',
  };
}

function formatPhonetic(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  
  const usPattern = /(?:美|US|us)\s*([/\[\(][^/\]\)]+[/\]\)])/;
  const ukPattern = /(?:英|UK|uk)\s*([/\[\(][^/\]\)]+[/\]\)])/;
  
  const usMatch = text.match(usPattern);
  const ukMatch = text.match(ukPattern);
  
  if (usMatch && ukMatch) {
    return `<span class="us">US ${usMatch[1]}</span><span class="uk">UK ${ukMatch[1]}</span>`;
  }
  if (usMatch) {
    return `<span class="us">${usMatch[1]}</span>`;
  }
  if (ukMatch) {
    return `<span class="uk">${ukMatch[1]}</span>`;
  }
  
  if (text.startsWith('/') || text.startsWith('[')) return text;
  return `/${text}/`;
}

function renderSkeleton(count = currentPageSize) {
  const rows = Math.max(3, Math.min(10, count || DEFAULT_PAGE_SIZE));
  entriesList.innerHTML = Array.from({ length: rows })
    .map(
      () => `
      <article class="wordbook-entry-card skeleton">
        <div class="wordbook-entry-side">
          <div class="wordbook-entry-order skeleton-dot"></div>
        </div>
        <div class="wordbook-entry-content">
          <div class="skeleton-line skeleton-line-lg"></div>
          <div class="skeleton-line skeleton-line-md"></div>
          <div class="skeleton-line skeleton-line-sm"></div>
        </div>
      </article>`
    )
    .join('');
}

async function loadSavedWords() {
  try {
    const data = await api(`/api/wordbooks/${wordbookId}/saved-words`);
    starredWords = new Set((data.words || []).map(normalizeWord));
  } catch (_) {
    starredWords = new Set();
  }
}

async function loadWordbook() {
  currentWordbook = await api(`/api/wordbooks/${wordbookId}`);
}

function renderEntries(page) {
  const items = page.items || [];
  currentEntryMap = new Map(items.map((entry) => [String(entry.id), entry]));
  if (!items.length) {
    if (onlySaved && !currentQuery) {
      entriesList.innerHTML = '<div class="empty-state"><h3>还没有收藏词</h3><p>在词书里点星标收藏后，可以在这里集中查看。</p></div>';
    } else {
      entriesList.innerHTML = currentQuery
        ? '<div class="empty-state"><h3>没有匹配词条</h3><p>换个关键词再试试，支持搜索英文、中文和释义。</p></div>'
        : '<div class="empty-state"><h3>暂无词条</h3><p>当前词书还没有可显示的单词。</p></div>';
    }
    return;
  }

  entriesList.innerHTML = items.map((entry, index) => {
    const rowNo = (page.page - 1) * page.page_size + index + 1;
    const wordKey = normalizeWord(entry.word);
    const isSaved = starredWords.has(wordKey);
    const isSaving = savingWords.has(wordKey);
    const starLabel = isSaved ? '取消收藏' : '点星标收藏';
    const { chinese, english } = formatEntryDisplay(entry);
    return `
      <article class="wordbook-entry-card${isSaved ? ' saved' : ''}">
        <div class="wordbook-entry-side">
          <div class="wordbook-entry-order">${rowNo}</div>
        </div>
        <div class="wordbook-entry-content">
          <div class="wordbook-entry-head">
            <div class="wordbook-entry-title">
              <div class="wordbook-entry-wordline">
                <div class="wordbook-entry-word">${escapeHtml(entry.word)}</div>
              </div>
              ${entry.pronunciation ? `<div class="wordbook-entry-phonetic">${formatPhonetic(entry.pronunciation)}</div>` : ''}
            </div>
            <div class="wordbook-entry-badges">
              <span class="wordbook-speak-slot">
                <button
                  type="button"
                  class="wordbook-speak-btn"
                  data-speak-word="${escapeHtml(entry.word)}"
                  aria-label="朗读"
                  title="朗读"
                >🔊</button>
              </span>
              <button type="button" class="btn-sm btn-primary" data-know-entry-id="${entry.id}">会</button>
              <button type="button" class="btn-sm btn-danger" data-unknown-entry-id="${entry.id}">不会</button>
              <span class="wordbook-save-slot">
                <button
                  type="button"
                  class="wordbook-save-btn${isSaved ? ' saved' : ''}${isSaving ? ' saving' : ''}"
                  data-save-entry-id="${entry.id}"
                  aria-label="${starLabel}"
                  aria-pressed="${isSaved ? 'true' : 'false'}"
                  ${isSaving ? 'disabled' : ''}
                >${isSaving ? '…' : (isSaved ? '★' : '☆')}</button>
                <span class="wordbook-save-tooltip" role="tooltip">${starLabel}</span>
              </span>
            </div>
          </div>
          <div class="wordbook-entry-translation">${escapeHtml(chinese || '暂无中文释义')}</div>
          ${english ? `<div class="wordbook-entry-definition">${escapeHtml(english)}</div>` : ''}
          ${entry.example ? `<div class="wordbook-entry-example">${escapeHtml(entry.example)}</div>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

function renderPageMeta(page) {
  currentPageState = page;
  currentPage = page.page;
  currentPageSize = page.page_size;
  pageStatus.textContent = `${onlySaved ? '已收藏 · ' : '全部 · '}第 ${page.page} / ${page.total_pages} 页 · 共 ${page.total} 个结果`;
  if (pageSizeSelect) pageSizeSelect.value = String(page.page_size);
  if (jumpPageInput) {
    jumpPageInput.max = String(Math.max(1, page.total_pages));
    jumpPageInput.placeholder = `1-${Math.max(1, page.total_pages)}`;
  }
}

function buildFallbackPageList(page, span = 2) {
  const pages = new Set([1, page.total_pages, page.page - 1, page.page, page.page + 1]);
  for (let cursor = page.page - span; cursor <= page.page + span; cursor += 1) {
    if (cursor >= 1 && cursor <= page.total_pages) pages.add(cursor);
  }
  return Array.from(pages).sort((a, b) => a - b);
}

function renderFallbackPagination(page) {
  const pages = buildFallbackPageList(page);
  paginationContainer.innerHTML = '';
  const frag = document.createDocumentFragment();

  const buttons = [
    { label: '首页', page: 1, disabled: page.page <= 1 },
    { label: '上一页', page: page.page - 1, disabled: page.page <= 1 },
    ...pages.map((item) => ({ label: String(item), page: item, active: item === page.page, disabled: item === page.page })),
    { label: '下一页', page: page.page + 1, disabled: page.page >= page.total_pages },
    { label: '末页', page: page.total_pages, disabled: page.page >= page.total_pages },
  ];

  buttons.forEach((item) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = item.active ? 'btn-primary btn-sm' : 'btn-secondary btn-sm';
    btn.textContent = item.label;
    btn.disabled = item.disabled;
    btn.addEventListener('click', async () => {
      if (item.page === currentPage || item.disabled) return;
      currentPage = item.page;
      await loadEntries({ scrollTop: true });
    });
    frag.appendChild(btn);
  });

  paginationContainer.appendChild(frag);
}

function renderPluginPagination(page) {
  if (!paginationContainer) return;
  if (paginationInstance?.destroy) {
    paginationInstance.destroy();
  }
  paginationContainer.innerHTML = '';
  paginationInstance = new window.tui.Pagination(paginationContainer, {
    totalItems: page.total,
    itemsPerPage: page.page_size,
    visiblePages: Math.min(7, Math.max(1, page.total_pages)),
    page: page.page,
    centerAlign: true,
    template: {
      page: '<a href="#" class="tui-page-btn">{{page}}</a>',
      currentPage: '<strong class="tui-page-btn tui-is-selected">{{page}}</strong>',
      moveButton: '<a href="#" class="tui-page-btn tui-{{type}}"><span class="tui-ico-{{type}}">{{type}}</span></a>',
      disabledMoveButton: '<span class="tui-page-btn tui-is-disabled tui-{{type}}"><span class="tui-ico-{{type}}">{{type}}</span></span>',
      moreButton: '<a href="#" class="tui-page-btn tui-{{type}}-is-ellip">...</a>',
    },
  });
  paginationInstance.on('afterMove', async (event) => {
    if (event.page === currentPage) return;
    currentPage = event.page;
    try {
      await loadEntries({ scrollTop: true });
    } catch (err) {
      setStatus(err.message, 'error');
    }
  });
}

function renderPagination(page) {
  if (!paginationContainer) return;
  if (!window.tui?.Pagination) {
    renderFallbackPagination(page);
    return;
  }
  renderPluginPagination(page);
}

async function loadEntries({ scrollTop = false, showSkeleton = true } = {}) {
  if (showSkeleton) renderSkeleton();
  const query = new URLSearchParams({
    page: String(currentPage),
    page_size: String(currentPageSize),
    q: currentQuery,
  });
  if (onlySaved) query.set('only_saved', 'true');
  const page = await api(`/api/wordbooks/${wordbookId}/entries?${query.toString()}`);
  renderEntries(page);
  renderPageMeta(page);
  renderPagination(page);
  syncUrl();
  if (scrollTop) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

async function refreshAll() {
  await loadWordbook();
  await loadSavedWords();
  await loadEntries();
}

function jumpToPage() {
  const target = parsePositiveInt(jumpPageInput?.value, currentPage);
  const totalPages = currentPageState?.total_pages || 1;
  const safePage = Math.min(Math.max(1, target), totalPages);
  if (safePage === currentPage) return;
  currentPage = safePage;
  loadEntries({ scrollTop: true }).catch((err) => setStatus(err.message, 'error'));
}

async function toggleWord(entryId) {
  const entry = currentEntryMap.get(String(entryId));
  if (!entry) return;
  const wordKey = normalizeWord(entry.word);
  if (!wordKey || savingWords.has(wordKey)) return;

  const wasSaved = starredWords.has(wordKey);
  savingWords.add(wordKey);
  if (currentPageState) renderEntries(currentPageState);

  try {
    if (wasSaved) {
      await api(`/api/vocab/by-word/${encodeURIComponent(entry.word)}`, { method: 'DELETE' });
      starredWords.delete(wordKey);
    } else {
      const saved = await api('/api/vocab/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word: entry.word,
          source_platform: 'wordbook',
          source_video_id: `wordbook-${wordbookId}`,
          source_url: `/wordbook?id=${wordbookId}`,
          source_title: currentWordbook?.name || '词书',
          sentence: entry.example || entry.definition || '',
          sentence_translation: entry.translation || '',
          definition: entry.definition || '',
          pronunciation: entry.pronunciation || '',
          part_of_speech: entry.part_of_speech || '',
          translation: entry.translation || '',
          wordbook_id: wordbookId,
        }),
      });
      starredWords.add(normalizeWord(saved.word || entry.word));
    }
    savingWords.delete(wordKey);
    await loadSavedWords();
    await loadWordbook();
    if (onlySaved) {
      await loadEntries({ showSkeleton: false });
    } else if (currentPageState) {
      renderEntries(currentPageState);
    }
  } catch (err) {
    savingWords.delete(wordKey);
    setStatus(`${wasSaved ? '取消收藏' : '收藏'}失败：${err.message}`, 'error');
    if (currentPageState) renderEntries(currentPageState);
  }
}

entrySearchInput?.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    currentQuery = entrySearchInput.value.trim();
    currentPage = 1;
    try {
      await loadEntries();
    } catch (err) {
      setStatus(err.message, 'error');
    }
  }, 220);
});

clearEntrySearchBtn?.addEventListener('click', async () => {
  entrySearchInput.value = '';
  currentQuery = '';
  currentPage = 1;
  try {
    await loadEntries();
  } catch (err) {
    setStatus(err.message, 'error');
  }
});

pageSizeSelect?.addEventListener('change', async () => {
  currentPageSize = sanitizePageSize(pageSizeSelect.value);
  currentPage = 1;
  try {
    await loadEntries();
  } catch (err) {
    setStatus(err.message, 'error');
  }
});

jumpPageBtn?.addEventListener('click', jumpToPage);

jumpPageInput?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    jumpToPage();
  }
});

function speakWord(word) {
  const w = String(word || '').trim();
  if (!w) return;
  try {
    if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
      window.AndroidDictionary.speak(w);
      return;
    }
  } catch (_) { /* fall through */ }
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(w);
  utterance.lang = 'en-US';
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

entriesList?.addEventListener('click', async (event) => {
  const speakBtn = event.target.closest('[data-speak-word]');
  if (speakBtn) {
    const word = speakBtn.dataset.speakWord;
    if (word) speakWord(word);
    return;
  }

  const unknownBtn = event.target.closest('[data-unknown-entry-id]');
  if (unknownBtn) {
    const entryId = parseInt(unknownBtn.dataset.unknownEntryId || '0', 10);
    const entry = currentEntryMap.get(String(entryId));
    if (!entry) return;
    try {
      await api('/api/vocab/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word: entry.word,
          source_platform: 'wordbook',
          source_video_id: `wordbook-${wordbookId}`,
          source_url: `/wordbook?id=${wordbookId}`,
          source_title: currentWordbook?.name || '词书',
          sentence: entry.example || entry.definition || '',
          sentence_translation: entry.translation || '',
          definition: entry.definition || '',
          pronunciation: entry.pronunciation || '',
          part_of_speech: entry.part_of_speech || '',
          translation: entry.translation || '',
          wordbook_id: wordbookId,
        }),
      });
      starredWords.add(normalizeWord(entry.word));
      setStatus(`「${entry.word}」已进生词本`, 'success');
      if (currentPageState) renderEntries(currentPageState);
    } catch (err) {
      setStatus(err.message, 'error');
    }
    return;
  }

  const knowBtn = event.target.closest('[data-know-entry-id]');
  if (knowBtn) {
    const entryId = parseInt(knowBtn.dataset.knowEntryId || '0', 10);
    const entry = currentEntryMap.get(String(entryId));
    if (!entry) return;
    try {
      await api(`/api/vocab/by-word/${encodeURIComponent(entry.word)}`, { method: 'DELETE' });
      starredWords.delete(normalizeWord(entry.word));
      setStatus(`「${entry.word}」标记为会`, 'success');
      if (currentPageState) renderEntries(currentPageState);
    } catch (_) {
      setStatus(`「${entry.word}」已会，继续下一个吧`, 'success');
    }
    return;
  }

  const button = event.target.closest('[data-save-entry-id]');
  if (!button) return;
  const entryId = parseInt(button.dataset.saveEntryId || '0', 10);
  if (!entryId) return;
  await toggleWord(entryId);
});

onlySavedToggle?.addEventListener('change', async () => {
  onlySaved = onlySavedToggle.checked;
  currentPage = 1;
  syncUrl();
  try {
    await loadEntries({ scrollTop: true });
  } catch (err) {
    setStatus(err.message, 'error');
  }
});

function renderDetailWordPreview(payload) {
  if (!detailWordPreview) return;
  if (!payload?.word) {
    detailWordPreview.hidden = true;
    detailWordPreview.innerHTML = '';
    return;
  }
  const chinese = payload.translation || payload.youdao_translation || '';
  const phonetic = payload.pronunciation || '';
  detailWordPreview.hidden = false;
  detailWordPreview.innerHTML = `
    <div class="wordbook-preview-word">${escapeHtml(payload.word)}</div>
    ${phonetic ? `<div class="wordbook-preview-phonetic">${escapeHtml(formatPhonetic(phonetic))}</div>` : ''}
    <div class="wordbook-preview-cn">${escapeHtml(chinese || '暂无中文释义')}</div>
  `;
}

async function previewDetailWord(word) {
  const cleaned = String(word || '').trim();
  if (!cleaned) {
    renderDetailWordPreview(null);
    return;
  }
  const requestId = ++detailPreviewRequestId;
  try {
    const payload = await api(`/api/word-enrich/${encodeURIComponent(cleaned)}`);
    if (requestId !== detailPreviewRequestId) return;
    renderDetailWordPreview(payload);
  } catch {
    if (requestId !== detailPreviewRequestId) return;
    renderDetailWordPreview({ word: cleaned });
  }
}

async function addWordFromDetail() {
  const word = detailAddWordInput?.value.trim();
  if (!word) {
    setStatus('请输入要添加的单词', 'error');
    return;
  }
  detailAddWordBtn.disabled = true;
  try {
    const entry = await api(`/api/wordbooks/${wordbookId}/entries/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word }),
    });
    renderDetailWordPreview(entry);
    detailAddWordInput.value = '';
    currentPage = 1;
    await refreshAll();
    setStatus('');
  } catch (err) {
    setStatus(err.message, 'error');
  } finally {
    detailAddWordBtn.disabled = false;
  }
}

async function importFilesFromDetail() {
  const files = Array.from(detailImportFileInput?.files || []);
  if (!files.length) return;
  try {
    for (const file of files) {
      const form = new FormData();
      form.append('file', file);
      const resp = await fetch(`/api/wordbooks/${wordbookId}/entries/upload`, { method: 'POST', body: form });
      if (!resp.ok) throw new Error(await resp.text() || `${file.name} 导入失败`);
    }
    detailImportFileInput.value = '';
    currentPage = 1;
    await refreshAll();
    setStatus('');
  } catch (err) {
    setStatus(err.message, 'error');
  }
}

detailAddWordInput?.addEventListener('input', () => {
  clearTimeout(detailPreviewTimer);
  const word = detailAddWordInput.value.trim();
  if (!word) {
    renderDetailWordPreview(null);
    return;
  }
  detailPreviewTimer = setTimeout(() => previewDetailWord(word), 320);
});

detailAddWordInput?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    addWordFromDetail();
  }
});

detailAddWordBtn?.addEventListener('click', addWordFromDetail);
detailImportFileInput?.addEventListener('change', importFilesFromDetail);

window.addEventListener('load', async () => {
  if (!wordbookId) {
    setStatus('缺少词书 id，请从词书首页重新进入。', 'error');
    return;
  }
  entrySearchInput.value = currentQuery;
  if (pageSizeSelect) pageSizeSelect.value = String(currentPageSize);
  if (onlySavedToggle) onlySavedToggle.checked = onlySaved;
  try {
    await refreshAll();
  } catch (err) {
    setStatus(err.message, 'error');
  }
});
