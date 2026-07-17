const createWordbookForm = document.getElementById('createWordbookForm');
const wordbookStatus = document.getElementById('wordbookStatus');
const catalogStatus = document.getElementById('catalogStatus');
const catalogWordbookSelect = document.getElementById('catalogWordbookSelect');
const catalogWordbookDetail = document.getElementById('catalogWordbookDetail');
const catalogInstalledList = document.getElementById('catalogInstalledList');
const installCatalogBtn = document.getElementById('installCatalogBtn');
const openCatalogWordbookBtn = document.getElementById('openCatalogWordbookBtn');
const myWordbookList = document.getElementById('myWordbookList');
const wordbookEditor = document.getElementById('wordbookEditor');
const activeWordbookTitle = document.getElementById('activeWordbookTitle');
const activeWordbookMeta = document.getElementById('activeWordbookMeta');
const addWordInput = document.getElementById('addWordInput');
const addWordBtn = document.getElementById('addWordBtn');
const wordPreview = document.getElementById('wordPreview');
const importFileInput = document.getElementById('importFileInput');
const importFileBtn = document.getElementById('importFileBtn');
const openActiveWordbookBtn = document.getElementById('openActiveWordbookBtn');
const deleteActiveWordbookBtn = document.getElementById('deleteActiveWordbookBtn');

let cachedWordbooks = [];
let cachedCatalog = [];
let activeWordbookId = 0;
let previewTimer = null;
let previewRequestId = 0;

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || '请求失败');
  }
  return resp.json();
}

function setStatus(message, type = '') {
  if (!wordbookStatus) return;
  if (type === 'success') return;
  wordbookStatus.textContent = message;
  wordbookStatus.className = `status-msg ${type}`.trim();
}

function setCatalogStatus(message, type = '') {
  if (!catalogStatus) return;
  catalogStatus.textContent = message;
  catalogStatus.className = `status-msg ${type}`.trim();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function formatPhonetic(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  if (text.startsWith('/') || text.startsWith('[')) return text;
  return `/${text.replace(/^\/|\/$/g, '')}/`;
}

function openWordbook(wordbookId) {
  if (!wordbookId) return;
  location.href = `/wordbook?id=${wordbookId}`;
}

function getActiveWordbook() {
  return cachedWordbooks.find((item) => item.id === activeWordbookId) || null;
}

function selectWordbook(wordbookId) {
  activeWordbookId = wordbookId;
  renderMyWordbooks(cachedWordbooks);
  renderEditor();
}

function renderMyWordbooks(items) {
  cachedWordbooks = items;
  if (!myWordbookList) return;
  if (!items.length) {
    myWordbookList.innerHTML = '<div class="empty-state"><p>还没有词书，先创建一个吧。</p></div>';
    if (wordbookEditor) wordbookEditor.hidden = true;
    activeWordbookId = 0;
    return;
  }
  if (!activeWordbookId || !items.some((item) => item.id === activeWordbookId)) {
    activeWordbookId = items[0].id;
  }
  myWordbookList.innerHTML = items.map((item) => `
    <div class="wordbook-item-wrap ${item.id === activeWordbookId ? 'active' : ''}">
      <button type="button" class="wordbook-item ${item.id === activeWordbookId ? 'active' : ''}" data-wordbook-id="${item.id}">
        <div class="wordbook-item-name">${escapeHtml(item.name)}</div>
        <div class="wordbook-item-meta">${item.entry_count} 词 · ${escapeHtml(item.source_name || '自定义')}</div>
      </button>
      <button type="button" class="wordbook-item-delete" data-delete-wordbook-id="${item.id}" title="删除词书" aria-label="删除词书">×</button>
    </div>
  `).join('');
  myWordbookList.querySelectorAll('[data-wordbook-id]').forEach((btn) => {
    btn.addEventListener('click', () => selectWordbook(parseInt(btn.dataset.wordbookId, 10)));
  });
  myWordbookList.querySelectorAll('[data-delete-wordbook-id]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteWordbook(parseInt(btn.dataset.deleteWordbookId, 10));
    });
  });
  renderEditor();
}

function renderEditor() {
  const book = getActiveWordbook();
  if (!wordbookEditor || !book) {
    if (wordbookEditor) wordbookEditor.hidden = true;
    return;
  }
  wordbookEditor.hidden = false;
  if (activeWordbookTitle) activeWordbookTitle.textContent = book.name;
  if (activeWordbookMeta) {
    activeWordbookMeta.textContent = `${book.entry_count} 个单词${book.description ? ` · ${book.description}` : ''}`;
  }
}

function renderWordPreview(payload) {
  if (!wordPreview) return;
  if (!payload?.word) {
    wordPreview.hidden = true;
    wordPreview.innerHTML = '';
    return;
  }
  const chinese = payload.translation || payload.youdao_translation || '';
  const phonetic = payload.pronunciation || '';
  wordPreview.hidden = false;
  wordPreview.innerHTML = `
    <div class="wordbook-preview-word">${escapeHtml(payload.word)}</div>
    ${phonetic ? `<div class="wordbook-preview-phonetic">${escapeHtml(formatPhonetic(phonetic))}</div>` : ''}
    <div class="wordbook-preview-cn">${escapeHtml(chinese || (payload.pending_enrichment ? '正在查询释义…' : '暂无中文释义'))}</div>
    ${payload.definition ? `<div class="wordbook-preview-en">${escapeHtml(payload.definition)}</div>` : ''}
  `;
}

async function previewWord(word) {
  const cleaned = String(word || '').trim();
  if (!cleaned) {
    renderWordPreview(null);
    return null;
  }
  const requestId = ++previewRequestId;
  try {
    const payload = await api(`/api/word-enrich/${encodeURIComponent(cleaned)}`);
    if (requestId !== previewRequestId) return null;
    renderWordPreview(payload);
    return payload;
  } catch {
    if (requestId !== previewRequestId) return null;
    renderWordPreview({ word: cleaned, pending_enrichment: false });
    return null;
  }
}

async function addWordToActiveBook() {
  const word = addWordInput?.value.trim();
  if (!activeWordbookId) {
    setStatus('请先创建或选择一个词书', 'error');
    return;
  }
  if (!word) {
    setStatus('请输入要添加的单词', 'error');
    return;
  }
  addWordBtn.disabled = true;
  try {
    const entry = await api(`/api/wordbooks/${activeWordbookId}/entries/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word }),
    });
    renderWordPreview(entry);
    addWordInput.value = '';
    await loadWordbooks();
    setStatus('');
  } catch (err) {
    setStatus(err.message, 'error');
  } finally {
    addWordBtn.disabled = false;
  }
}

async function importFiles() {
  if (!activeWordbookId) {
    setStatus('请先创建或选择一个词书', 'error');
    return;
  }
  const files = Array.from(importFileInput?.files || []);
  if (!files.length) {
    setStatus('请选择要导入的文件', 'error');
    return;
  }
  importFileBtn.disabled = true;
  let total = 0;
  try {
    for (const file of files) {
      const form = new FormData();
      form.append('file', file);
      const result = await fetch(`/api/wordbooks/${activeWordbookId}/entries/upload`, {
        method: 'POST',
        body: form,
      });
      if (!result.ok) {
        const text = await result.text();
        throw new Error(text || `${file.name} 导入失败`);
      }
      const data = await result.json();
      total += data.count || 0;
    }
    if (importFileInput) importFileInput.value = '';
    await loadWordbooks();
    setStatus('');
    wordbookStatus.textContent = `已从 ${files.length} 个文件导入 ${total} 个单词`;
    wordbookStatus.className = 'status-msg';
  } catch (err) {
    setStatus(err.message, 'error');
  } finally {
    importFileBtn.disabled = false;
  }
}

const GITHUB_CATALOG_OPTIONS = [
  {
    group: '大学考试',
    items: [
      { key: 'cet4_kylebing', label: '大学英语四级（CET-4）' },
      { key: 'cet6_kylebing', label: '大学英语六级（CET-6）' },
      { key: 'kaoyan_kylebing', label: '考研英语' },
      { key: 'tem4_kylebing', label: '英语专业四级（专四）' },
      { key: 'tem8_kylebing', label: '英语专业八级（专八）' },
    ],
  },
  {
    group: '出国留学',
    items: [
      { key: 'ielts_kylebing', label: '雅思 IELTS' },
      { key: 'toefl_kylebing', label: '托福 TOEFL' },
      { key: 'gre_kylebing', label: 'GRE' },
      { key: 'gmat_kylebing', label: 'GMAT' },
      { key: 'sat_kylebing', label: 'SAT' },
    ],
  },
  {
    group: '中小学 / 商务',
    items: [
      { key: 'gaozhong_kylebing', label: '高中英语' },
      { key: 'chuzhong_kylebing', label: '初中英语' },
      { key: 'bec_kylebing', label: 'BEC 商务英语' },
    ],
  },
];

function getCatalogItem(key) {
  return cachedCatalog.find((item) => item.key === key) || null;
}

function getSelectedCatalogKey() {
  return catalogWordbookSelect?.value || '';
}

function renderCatalogPicker() {
  if (!catalogWordbookSelect) return;
  const options = ['<option value="">选择 GitHub 词书</option>'];
  GITHUB_CATALOG_OPTIONS.forEach((group) => {
    options.push(`<optgroup label="${escapeHtml(group.group)}">`);
    group.items.forEach((item) => {
      const catalog = getCatalogItem(item.key);
      const count = catalog?.entry_count ? ` · ${catalog.entry_count} 词` : '';
      const status = catalog?.installed_wordbook_id ? ' · 已导入' : '';
      options.push(`<option value="${item.key}">${escapeHtml(item.label)}${count}${status}</option>`);
    });
    options.push('</optgroup>');
  });
  const previous = getSelectedCatalogKey();
  catalogWordbookSelect.innerHTML = options.join('');
  if (previous && getCatalogItem(previous)) {
    catalogWordbookSelect.value = previous;
  }
  renderCatalogDetail();
  renderInstalledCatalogList();
}

function renderCatalogDetail() {
  if (!catalogWordbookDetail) return;
  const key = getSelectedCatalogKey();
  const item = getCatalogItem(key);
  if (!item) {
    catalogWordbookDetail.innerHTML = '<p class="video-meta">从下拉菜单选择词书，查看说明后导入学习。</p>';
    if (openCatalogWordbookBtn) openCatalogWordbookBtn.disabled = true;
    return;
  }
  const installed = !!item.installed_wordbook_id;
  catalogWordbookDetail.innerHTML = `
    <div class="wordbook-catalog-detail-card">
      <div class="wordbook-catalog-detail-title">${escapeHtml(item.name)}</div>
      <div class="wordbook-catalog-detail-meta">
        <span>${item.entry_count || 0} 词</span>
        <span>${escapeHtml(item.category || item.source_name || 'GitHub')}</span>
        <span class="status-badge ${installed ? 'done' : 'processing'}">${installed ? '已导入' : '可导入'}</span>
      </div>
      <p class="video-meta">${escapeHtml(item.description || '')}</p>
      <a class="btn-secondary btn-sm" href="${item.repo_url}" target="_blank" rel="noreferrer">查看 GitHub 源仓库</a>
    </div>
  `;
  if (installCatalogBtn) installCatalogBtn.textContent = installed ? '重新同步' : '导入词书';
  if (openCatalogWordbookBtn) openCatalogWordbookBtn.disabled = !installed;
}

function renderInstalledCatalogList() {
  if (!catalogInstalledList) return;
  const installed = cachedCatalog.filter((item) => item.installed_wordbook_id);
  if (!installed.length) {
    catalogInstalledList.innerHTML = '';
    return;
  }
  catalogInstalledList.innerHTML = `
    <div class="wordbook-catalog-installed-title">已导入的 GitHub 词书</div>
    <div class="wordbook-catalog-installed-grid">
      ${installed.map((item) => `
        <button type="button" class="wordbook-item" data-open-installed="${item.installed_wordbook_id}" data-select-key="${item.key}">
          <div class="wordbook-item-name">${escapeHtml(item.name)}</div>
          <div class="wordbook-item-meta">${item.entry_count || 0} 词 · 点击打开</div>
        </button>
      `).join('')}
    </div>
  `;
  catalogInstalledList.querySelectorAll('[data-open-installed]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (catalogWordbookSelect && btn.dataset.selectKey) {
        catalogWordbookSelect.value = btn.dataset.selectKey;
        renderCatalogDetail();
      }
      openWordbook(parseInt(btn.dataset.openInstalled, 10));
    });
  });
}

function renderCatalog(items) {
  cachedCatalog = items;
  renderCatalogPicker();
}

async function deleteWordbook(wordbookId) {
  const book = cachedWordbooks.find((item) => item.id === wordbookId);
  if (!book) return;
  const confirmed = window.confirm(`确定删除词书「${book.name}」吗？\n删除后列表不再显示，数据仍保留在本地。`);
  if (!confirmed) return;

  if (deleteActiveWordbookBtn) deleteActiveWordbookBtn.disabled = true;
  try {
    await api(`/api/wordbooks/${wordbookId}`, { method: 'DELETE' });
    if (activeWordbookId === wordbookId) {
      activeWordbookId = 0;
      renderWordPreview(null);
      if (addWordInput) addWordInput.value = '';
    }
    await loadWordbooks();
    setStatus('');
    wordbookStatus.textContent = `已删除词书「${book.name}」`;
    wordbookStatus.className = 'status-msg';
  } catch (err) {
    setStatus(err.message, 'error');
  } finally {
    if (deleteActiveWordbookBtn) deleteActiveWordbookBtn.disabled = false;
  }
}

async function loadWordbooks() {
  const items = await api('/api/wordbooks?custom=1');
  renderMyWordbooks(items);
}

async function loadCatalog() {
  const items = await api('/api/wordbooks/catalog');
  renderCatalog(items);
}

async function installCatalogWordbook(key) {
  if (!key) {
    setCatalogStatus('请先选择要导入的词书', 'error');
    return;
  }
  installCatalogBtn.disabled = true;
  setCatalogStatus('');
  try {
    const data = await api(`/api/wordbooks/catalog/${encodeURIComponent(key)}/install`, { method: 'POST' });
    await loadCatalog();
    setCatalogStatus(`已导入 ${data.imported_count} 条词汇，可在下方或点击「打开词书」开始学习`, '');
  } catch (err) {
    setCatalogStatus(err.message, 'error');
  } finally {
    installCatalogBtn.disabled = false;
  }
}

catalogWordbookSelect?.addEventListener('change', renderCatalogDetail);
installCatalogBtn?.addEventListener('click', () => installCatalogWordbook(getSelectedCatalogKey()));
openCatalogWordbookBtn?.addEventListener('click', () => {
  const item = getCatalogItem(getSelectedCatalogKey());
  if (item?.installed_wordbook_id) openWordbook(item.installed_wordbook_id);
});

createWordbookForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(createWordbookForm);
  try {
    const created = await api('/api/wordbooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.get('name'),
        description: form.get('description') || '',
        language: 'en',
        source_name: '自定义',
      }),
    });
    createWordbookForm.reset();
    await loadWordbooks();
    selectWordbook(created.id);
    addWordInput?.focus();
    setStatus('');
  } catch (err) {
    setStatus(err.message, 'error');
  }
});

addWordInput?.addEventListener('input', () => {
  clearTimeout(previewTimer);
  const word = addWordInput.value.trim();
  if (!word) {
    renderWordPreview(null);
    return;
  }
  previewTimer = setTimeout(() => previewWord(word), 320);
});

addWordInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    addWordToActiveBook();
  }
});

addWordBtn?.addEventListener('click', addWordToActiveBook);
importFileBtn?.addEventListener('click', importFiles);
openActiveWordbookBtn?.addEventListener('click', () => openWordbook(activeWordbookId));
deleteActiveWordbookBtn?.addEventListener('click', () => {
  if (activeWordbookId) deleteWordbook(activeWordbookId);
});

window.addEventListener('load', async () => {
  try {
    const legacyId = parseInt(new URLSearchParams(window.location.search).get('book') || '0', 10);
    if (legacyId) {
      openWordbook(legacyId);
      return;
    }
    const [catalogResult, wordbooksResult] = await Promise.allSettled([
      loadCatalog(),
      loadWordbooks(),
    ]);
    const errors = [catalogResult, wordbooksResult]
      .filter((result) => result.status === 'rejected')
      .map((result) => result.reason?.message)
      .filter(Boolean);
    if (errors.length) setStatus(errors.join('；'), 'error');
  } catch (err) {
    setStatus(err.message, 'error');
  }
});
