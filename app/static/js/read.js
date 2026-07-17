// ── 阅读库页 /read — 书架布局 ──
const createBtn = document.getElementById('createReadingBtn');
const uploadBtn = document.getElementById('uploadReadingBtn');
const readingTitle = document.getElementById('readingTitle');
const readingContent = document.getElementById('readingContent');
const uploadTitle = document.getElementById('uploadTitle');
const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const uploadFileName = document.getElementById('uploadFileName');
const readingList = document.getElementById('readingList');
const readingListCount = document.getElementById('readingListCount');
const statusMsg = document.getElementById('statusMsg');
const pastePanel = document.getElementById('pastePanel');
const uploadPanel = document.getElementById('uploadPanel');
const shelfSearch = document.getElementById('shelfSearch');
const libraryBookList = document.getElementById('libraryBookList');

let pollTimer = null;
let libraryPollTimer = null;
let allDocs = [];
let catalogBooks = [];
const importingBookKeys = new Set();
const BUSY = new Set(['pending', 'translating']);

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    try {
      const data = JSON.parse(text);
      const detail = data.detail;
      if (typeof detail === 'string') throw new Error(detail);
      if (Array.isArray(detail)) throw new Error(detail.map((d) => d.msg || d).join('；'));
    } catch (err) {
      if (err instanceof Error && err.message !== text) throw err;
    }
    throw new Error(text.slice(0, 240) || `请求失败 (${resp.status})`);
  }
  return resp.json();
}

function showStatus(msg, type = '') {
  statusMsg.textContent = msg;
  statusMsg.className = 'status-msg ' + type;
  if (window.UI && msg) {
    UI.toast(msg, type === 'error' ? 'error' : type === 'success' ? 'success' : 'info');
  }
}

function renderShelfSkeleton(host, count = 3) {
  if (!host) return;
  host.innerHTML = Array.from({ length: count })
    .map(
      () => `
      <div class="reading-book-card skeleton">
        <div class="reading-book-card-header">
          <div class="skeleton-block skeleton-cover"></div>
          <div class="reading-book-headcopy">
            <div class="skeleton-line skeleton-line-lg"></div>
            <div class="skeleton-line skeleton-line-md"></div>
          </div>
        </div>
        <div class="reading-book-body">
          <div class="skeleton-line skeleton-line-sm"></div>
        </div>
        <div class="reading-book-foot">
          <div class="skeleton-line skeleton-line-md"></div>
        </div>
      </div>`
    )
    .join('');
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function hasPartialTranslation(doc) {
  const msg = doc?.status_message || '';
  return doc?.translate_status === 'done' && (msg.includes('未译出') || msg.includes('段失败'));
}

function statusLabel(doc) {
  const map = { pending: '排队', ready: '可读', translating: '翻译中', done: '完成', failed: '失败' };
  if (hasPartialTranslation(doc)) return '部分完成';
  return map[doc.translate_status] || doc.translate_status;
}

function statusClass(doc) {
  if (doc.translate_status === 'failed') return 'failed';
  if (hasPartialTranslation(doc)) return 'processing';
  if (BUSY.has(doc.translate_status)) return 'processing';
  return 'done';
}

function canRead(doc) {
  return doc.block_count > 0 && doc.translate_status !== 'failed';
}

function canRetranslate(doc) {
  if (doc.translate_status === 'translating') return false;
  if (doc.block_count > 0 && doc.translated_blocks >= doc.block_count) return false;
  if (hasPartialTranslation(doc)) return true;
  return ['done', 'failed', 'ready', 'pending'].includes(doc.translate_status);
}

function retranslateLabel(doc) {
  if (doc.translate_status === 'ready' && !(doc.translated_blocks > 0)) return '开始翻译';
  if (doc.translate_status === 'pending' && !(doc.translate_progress > 0)) return '重新排队';
  return '补译未译段落';
}

function bookIcon(doc) {
  const t = (doc.source_type || '').toLowerCase();
  if (t === 'github-book') return '📚';
  if (t === 'pdf') return '📕';
  if (t === 'epub') return '📗';
  if (t === 'web') return '🌐';
  return '📘';
}

function filteredDocs() {
  const q = (shelfSearch?.value || '').trim().toLowerCase();
  if (!q) return allDocs;
  return allDocs.filter((d) =>
    (d.title || '').toLowerCase().includes(q) ||
    (d.source_filename || '').toLowerCase().includes(q)
  );
}

function listSignature(docs) {
  return JSON.stringify(
    docs.map((d) => [d.id, d.title, d.translate_status, d.translate_progress, d.read_progress, d.block_count, d.status_message])
  );
}

let lastListSignature = null;

function renderList(docs, { force = false } = {}) {
  const signature = listSignature(docs);
  if (!force && signature === lastListSignature) return;
  lastListSignature = signature;
  readingListCount.textContent = docs.length;
  if (!docs.length) {
    readingList.innerHTML = '<div class="empty-state"><p>还没有本地导入内容，粘贴英文文本或上传文件吧</p></div>';
    return;
  }
  readingList.innerHTML = '';
  docs.forEach((doc) => {
    const card = document.createElement('div');
    const sourceType = (doc.source_type || '').toLowerCase();
    card.className = `reading-book-card reading-book-card--${sourceType || 'local'}`;
    const progress = doc.read_progress || 0;
    const partialMsg = hasPartialTranslation(doc) && doc.status_message
      ? `<div class="reading-book-notice" title="${escapeHtml(doc.status_message)}">${escapeHtml(doc.status_message)}</div>`
      : '';
    const failMsg = doc.translate_status === 'failed' && doc.status_message
      ? `<div class="reading-book-error" title="${escapeHtml(doc.status_message)}">${escapeHtml(doc.status_message.slice(0, 80))}${doc.status_message.length > 80 ? '…' : ''}</div>`
      : '';
    const progressBlock = progress > 0 ? `
        <div class="reading-book-progress-wrap">
          <div class="reading-book-progress-label">
            <span>阅读进度</span>
            <span>${progress}% · 第 ${Math.max(1, doc.last_block_index + 1)} 段</span>
          </div>
          <div class="reading-book-progress">
            <div class="reading-book-progress-fill" style="width:${progress}%"></div>
          </div>
        </div>
      ` : BUSY.has(doc.translate_status) ? `
        <div class="reading-book-progress-wrap">
          <div class="reading-book-progress-label">
            <span>翻译进度</span>
            <span>${doc.translate_progress}%</span>
          </div>
          <div class="reading-book-progress reading-book-progress--busy">
            <div class="reading-book-progress-fill" style="width:${doc.translate_progress}%"></div>
          </div>
        </div>
      ` : '';
    card.innerHTML = `
      <div class="reading-book-card-accent"></div>
      <div class="reading-book-card-header">
        <div class="reading-book-cover">${bookIcon(doc)}</div>
        <div class="reading-book-headcopy">
          <div class="reading-book-title-row">
            <div class="reading-book-title" title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</div>
            <button class="reading-title-edit btn-secondary btn-sm" data-edit-title="${doc.id}" title="改标题" aria-label="改标题">✏️</button>
          </div>
          <div class="reading-book-meta">
            <span class="reading-book-chip">${doc.block_count} 段</span>
            <span class="reading-book-chip">${doc.word_count} 词</span>
            <span class="status-badge ${statusClass(doc)}">${statusLabel(doc)}</span>
          </div>
        </div>
      </div>
      <div class="reading-book-body">
        ${partialMsg}
        ${failMsg}
        ${progressBlock}
      </div>
      <div class="reading-book-foot">
        <div class="reading-book-actions">
          ${canRead(doc) ? `<a class="btn-primary btn-sm" href="/reader?id=${doc.id}">${progress > 0 ? '继续阅读' : '开始阅读'}</a>` : ''}
          ${canRetranslate(doc) ? `<button class="btn-secondary btn-sm" data-retranslate="${doc.id}">${retranslateLabel(doc)}</button>` : ''}
          <button class="btn-danger btn-sm" data-delete="${doc.id}">删除</button>
        </div>
      </div>
    `;
    card.querySelector('[data-delete]')?.addEventListener('click', async (e) => {
      const id = e.currentTarget.dataset.delete;
      const ok = await UI.confirmDialog({
        title: '删除阅读材料',
        message: `确定删除《${doc.title}》吗？\n删除后列表不再显示，阅读内容与进度仍保留在本地。`,
        confirmText: '删除',
        danger: true,
      });
      if (!ok) return;
      const deleteVocab = await UI.confirmDialog({
        title: '是否同时删除生词',
        message: '要连同本书收藏的生词一起删除吗？\n选择「仅删书籍」会保留已收藏的生词。',
        confirmText: '一并删除生词',
        cancelText: '仅删书籍',
      });
      try {
        await api(`/api/readings/${id}?delete_vocab=${deleteVocab}`, { method: 'DELETE' });
        refreshList();
        showStatus('已从列表移除', 'success');
      } catch (err) {
        showStatus('删除失败: ' + err.message, 'error');
      }
    });
    card.querySelector('[data-retranslate]')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const id = btn.dataset.retranslate;
      if (!id || btn.disabled) return;
      btn.disabled = true;
      try {
        const resp = await api(`/api/readings/${id}/translate`, { method: 'POST' });
        showStatus(resp.queued === false ? '所有段落均已翻译' : '已开始补译未译段落', 'success');
        lastListSignature = null;
        await refreshList();
        if (!pollTimer) pollTimer = setInterval(refreshList, 3000);
      } catch (err) {
        showStatus('补译失败: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
    card.querySelector('[data-edit-title]')?.addEventListener('click', async (e) => {
      const id = parseInt(e.currentTarget.dataset.editTitle, 10);
      const docItem = allDocs.find((d) => d.id === id);
      const newTitle = await UI.promptDialog({
        title: '修改标题',
        value: docItem?.title || '',
        placeholder: '输入新的书名',
        confirmText: '保存',
      });
      if (newTitle == null || !newTitle.trim()) return;
      try {
        await api(`/api/readings/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: newTitle.trim() }),
        });
        refreshList();
      } catch (err) {
        showStatus('修改失败: ' + err.message, 'error');
      }
    });
    readingList.appendChild(card);
  });
}

function formatLibraryProgress(book) {
  if (!book.reading_document_id) return '';
  const total = book.reading_block_count || 0;
  const translated = book.reading_translated_blocks || 0;
  const pct = book.reading_translate_progress || 0;
  const readPct = book.reading_read_progress || 0;
  const msg = book.reading_status_message || '';
  const translateLine = total > 0
    ? `<div class="reading-book-progress-label"><span>翻译</span><span>${translated}/${total} · ${pct}%</span></div>
       <div class="reading-book-progress"><div class="reading-book-progress-fill" style="width:${pct}%"></div></div>`
    : '';
  const readLine = readPct > 0
    ? `<div class="reading-book-progress-label"><span>阅读</span><span>${readPct}%</span></div>
       <div class="reading-book-progress reading-book-progress--read"><div class="reading-book-progress-fill" style="width:${readPct}%"></div></div>`
    : '';
  const msgLine = msg ? `<div class="reading-book-notice" title="${escapeHtml(msg)}">${escapeHtml(msg.slice(0, 72))}${msg.length > 72 ? '…' : ''}</div>` : '';
  return `<div class="reading-book-progress-wrap">${msgLine}${translateLine}${readLine}</div>`;
}

function renderLibraryBooks(items) {
  catalogBooks = items;
  if (!libraryBookList) return;
  if (!items.length) {
    libraryBookList.innerHTML = '<div class="empty-state"><p>当前没有可导入的 GitHub 原著。</p></div>';
    return;
  }
  libraryBookList.innerHTML = '';
  items.forEach((book) => {
    const imported = !!book.reading_document_id;
    const cached = book.cache_status === 'cached';
    const failed = book.cache_status === 'failed';
    const card = document.createElement('div');
    card.className = `reading-book-card reading-book-card--library${imported ? ' reading-book-card--imported' : ''}`;
    card.innerHTML = `
      <div class="reading-book-card-accent"></div>
      <div class="reading-book-card-header">
        <div class="reading-book-cover reading-book-cover--library">📚</div>
        <div class="reading-book-headcopy">
          <div class="reading-book-title-row">
            <div class="reading-book-title" title="${escapeHtml(book.title)}">${escapeHtml(book.title)}</div>
          </div>
          <div class="reading-book-meta">
            <span class="reading-book-chip">${escapeHtml(book.author || 'Unknown')}</span>
            <span class="reading-book-chip">${book.cache_bytes ? `${Math.round(book.cache_bytes / 1024)} KB` : '未缓存'}</span>
            <span class="status-badge ${imported ? 'done' : failed ? 'failed' : cached ? 'processing' : ''}">${imported ? '已导入' : failed ? '失败' : cached ? '已缓存' : '可导入'}</span>
          </div>
        </div>
      </div>
      <div class="reading-book-body">
        <p class="reading-book-desc">${escapeHtml(book.description || '经典公共领域英文原著，导入后可双语阅读。')}</p>
        ${formatLibraryProgress(book)}
        ${failed && book.last_error ? `<div class="reading-book-error">${escapeHtml(book.last_error.slice(0, 100))}</div>` : ''}
      </div>
      <div class="reading-book-foot">
        <div class="reading-book-actions">
          <button class="btn-primary btn-sm" data-import-book="${book.key}">${imported ? '继续阅读' : '导入到阅读库'}</button>
          ${imported ? `<button class="btn-secondary btn-sm" data-fill-book="${book.key}">补译</button>` : ''}
          ${imported ? `<button class="btn-secondary btn-sm" data-reimport-book="${book.key}">重新导入</button>` : ''}
          <button class="btn-secondary btn-sm" data-refresh-book="${book.key}">重下载</button>
          ${imported ? `<button class="btn-danger btn-sm" data-unlink-book="${book.key}">移出书架</button>` : ''}
          <a class="btn-secondary btn-sm" href="${book.repo_url}" target="_blank" rel="noreferrer">源</a>
        </div>
      </div>
    `;
    card.querySelector('[data-import-book]')?.addEventListener('click', (e) => {
      const btn = e.currentTarget;
      if (importingBookKeys.has(book.key)) return;
      btn.disabled = true;
      if (imported && book.reading_document_id) {
        location.href = `/reader?id=${book.reading_document_id}`;
        return;
      }
      importLibraryBook(book).finally(() => { btn.disabled = false; });
    });
    card.querySelector('[data-fill-book]')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      if (!book.reading_document_id) return;
      btn.disabled = true;
      try {
        await api(`/api/readings/${book.reading_document_id}/translate`, { method: 'POST' });
        showStatus('已开始补译未译段落', 'success');
        await loadLibraryBooks();
      } catch (err) {
        showStatus('补译失败: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
    card.querySelector('[data-reimport-book]')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      if (importingBookKeys.has(book.key)) return;
      const ok = await UI.confirmDialog({
        title: '重新导入',
        message: '将删除当前阅读记录并重新从 GitHub 下载导入，确定吗？',
        confirmText: '重新导入',
        danger: true,
      });
      if (!ok) return;
      btn.disabled = true;
      importingBookKeys.add(book.key);
      try {
        const data = await api(`/api/readings/library/books/${encodeURIComponent(book.key)}/reimport`, { method: 'POST' });
        await loadLibraryBooks();
        if (data.reading?.id) location.href = `/reader?id=${data.reading.id}`;
      } catch (err) {
        showStatus('重新导入失败: ' + err.message, 'error');
      } finally {
        importingBookKeys.delete(book.key);
        btn.disabled = false;
      }
    });
    card.querySelector('[data-refresh-book]')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        await api(`/api/readings/library/books/${encodeURIComponent(book.key)}/refresh`, { method: 'POST' });
        showStatus('已重新下载缓存', 'success');
        await loadLibraryBooks();
      } catch (err) {
        showStatus('重下载失败: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
    card.querySelector('[data-unlink-book]')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const ok = await UI.confirmDialog({
        title: '移出书架',
        message: '从 GitHub 书库移出此书（可选择是否删除阅读内容与译文）',
        confirmText: '仅移出',
      });
      if (!ok) return;
      const deleteReading = await UI.confirmDialog({
        title: '删除阅读内容',
        message: '是否同时删除已导入的阅读内容与译文？',
        confirmText: '一并删除',
        danger: true,
      });
      btn.disabled = true;
      try {
        await api(`/api/readings/library/books/${encodeURIComponent(book.key)}/import?delete_reading=${deleteReading ? 'true' : 'false'}`, { method: 'DELETE' });
        showStatus('已移出书库书架', 'success');
        await loadLibraryBooks();
      } catch (err) {
        showStatus('移出失败: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
    libraryBookList.appendChild(card);
  });
}

async function loadLibraryBooks() {
  try {
    const items = await api('/api/readings/library/books');
    renderLibraryBooks(items);
    const busy = items.some((b) => b.reading_translate_status === 'translating' || b.reading_translate_status === 'pending');
    if (busy && !libraryPollTimer) libraryPollTimer = setInterval(loadLibraryBooks, 4000);
    else if (!busy && libraryPollTimer) { clearInterval(libraryPollTimer); libraryPollTimer = null; }
  } catch (e) {
    if (libraryBookList) {
      libraryBookList.innerHTML = `<div class="empty-state"><p>书库加载失败: ${escapeHtml(e.message)}</p></div>`;
    }
  }
}

async function importLibraryBook(book) {
  if (!book?.key || importingBookKeys.has(book.key)) return;
  importingBookKeys.add(book.key);
  const isLarge = (book.cache_bytes || 0) > 500_000;
  showStatus(isLarge ? `正在导入《${book.title}》，大型书籍可能需要 1–2 分钟…` : `正在导入《${book.title}》…`, '');
  renderLibraryBooks(catalogBooks);
  try {
    const data = await api(`/api/readings/library/books/${encodeURIComponent(book.key)}/import`, { method: 'POST' });
    await loadLibraryBooks();
    if (data.reading?.id) {
      const blocks = data.reading.block_count || 0;
      if (blocks > 500) {
        showStatus(`已导入 ${blocks.toLocaleString()} 段，按需翻译中…`, 'success');
      }
      location.href = `/reader?id=${data.reading.id}`;
      return;
    }
    showStatus(`已导入 ${book.title}`, 'success');
  } catch (e) {
    showStatus('导入书籍失败: ' + e.message, 'error');
  } finally {
    importingBookKeys.delete(book.key);
    renderLibraryBooks(catalogBooks);
  }
}

async function refreshList() {
  try {
    allDocs = await api('/api/readings?local=1');
    renderList(filteredDocs());
    const busy = allDocs.some((d) => BUSY.has(d.translate_status));
    if (busy && !pollTimer) pollTimer = setInterval(refreshList, 3000);
    else if (!busy && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  } catch (e) {
    readingList.innerHTML = `<div class="empty-state"><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
  }
}

shelfSearch?.addEventListener('input', () => renderList(filteredDocs()));

document.querySelectorAll('.reading-input-tabs .tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.reading-input-tabs .tab-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    pastePanel.classList.toggle('hidden', tab !== 'paste');
    uploadPanel.classList.toggle('hidden', tab !== 'upload');
  });
});

if (uploadZone && fileInput) {
  uploadZone.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files[0]) {
      fileInput.files = e.dataTransfer.files;
      uploadFileName.textContent = e.dataTransfer.files[0].name;
    }
  });
  fileInput.addEventListener('change', () => {
    uploadFileName.textContent = fileInput.files[0]?.name || '';
  });
}

createBtn.addEventListener('click', async () => {
  const content = readingContent.value.trim();
  if (!content) { showStatus('请输入英文内容', 'error'); return; }
  createBtn.disabled = true;
  try {
    const doc = await api('/api/readings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: readingTitle.value.trim() || 'Untitled', content }),
    });
    location.href = `/reader?id=${doc.id}`;
  } catch (e) {
    showStatus('创建失败: ' + e.message, 'error');
  } finally {
    createBtn.disabled = false;
  }
});

uploadBtn.addEventListener('click', async () => {
  const file = fileInput.files[0];
  if (!file) { showStatus('请选择文件', 'error'); return; }
  uploadBtn.disabled = true;
  const largeHint = file.size > 5 * 1024 * 1024 ? '大型文件正在解析入库，请稍候…' : '正在上传…';
  showStatus(largeHint, '');
  try {
    const form = new FormData();
    form.append('file', file);
    form.append('title', uploadTitle.value.trim());
    const resp = await fetch('/api/readings/upload', { method: 'POST', body: form });
    if (!resp.ok) {
      const text = await resp.text();
      try {
        const data = JSON.parse(text);
        throw new Error(typeof data.detail === 'string' ? data.detail : text);
      } catch (err) {
        if (err instanceof Error && err.message !== text) throw err;
        throw new Error(text.slice(0, 240) || '上传失败');
      }
    }
    const doc = await resp.json();
    location.href = `/reader?id=${doc.id}`;
  } catch (e) {
    showStatus('上传失败: ' + e.message, 'error');
  } finally {
    uploadBtn.disabled = false;
  }
});

window.addEventListener('load', async () => {
  renderShelfSkeleton(libraryBookList, 3);
  renderShelfSkeleton(readingList, 3);
  try {
    await loadLibraryBooks();
    await refreshList();
  } catch (e) {
    readingList.innerHTML = `<div class="empty-state"><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
  }
});
