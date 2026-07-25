function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(message, type = 'info') {
  const host = document.getElementById('toastHost');
  if (!host) {
    const toastHost = document.createElement('div');
    toastHost.id = 'toastHost';
    toastHost.className = 'ui-toast-host';
    document.body.appendChild(toastHost);
  }
  
  const toast = document.createElement('div');
  toast.className = `ui-toast ui-toast-${type}`;
  toast.innerHTML = `<span class="ui-toast-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span><span>${escapeHtml(message)}</span>`;
  
  document.getElementById('toastHost').appendChild(toast);
  
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 220);
  }, 2500);
}

function speakWord(word) {
  if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
    try {
      window.AndroidDictionary.speak(word);
      return;
    } catch (e) {
      console.log('Android TTS failed, falling back to Web Speech API');
    }
  }
  
  if (!('speechSynthesis' in window)) {
    showToast('您的设备不支持语音合成', 'error');
    return;
  }
  
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = 'en-US';
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

function renderWordPopover(data) {
  const body = document.getElementById('wordPopoverBody');
  if (!body) return;
  
  const phoneticHtml = data.pronunciation ? formatPhonetic(data.pronunciation) : '';
  
  let examplesHtml = '';
  if (data.example) {
    examplesHtml = `
      <div class="word-popover-examples">
        <div class="word-popover-example">${escapeHtml(data.example)}</div>
      </div>
    `;
  }
  
  body.innerHTML = `
    <div class="word-popover-word-row">
      <div class="word-popover-word">${escapeHtml(data.word)}</div>
    </div>
    ${phoneticHtml ? `<div class="word-popover-phonetic">${phoneticHtml}</div>` : ''}
    <div class="word-popover-def">${escapeHtml(data.translation)}</div>
    ${examplesHtml}
  `;
}

function showWordPopover(data, x, y) {
  const popover = document.getElementById('wordPopover');
  if (!popover) return;
  
  renderWordPopover(data);
  popover.classList.remove('hidden');
  
  const rect = popover.getBoundingClientRect();
  const maxX = window.innerWidth - rect.width - 20;
  const maxY = window.innerHeight - rect.height - 20;
  
  popover.style.left = `${Math.min(x, maxX)}px`;
  popover.style.top = `${Math.min(y, maxY)}px`;
  
  updateSaveButton(data.word);
}

function hideWordPopover() {
  const popover = document.getElementById('wordPopover');
  if (popover) {
    popover.classList.add('hidden');
  }
}

async function updateSaveButton(word) {
  const btn = document.getElementById('saveWordBtn');
  if (!btn) return;
  
  const saved = await isWordSaved(word);
  btn.innerHTML = saved ? '★' : '☆';
  btn.className = saved ? 'btn-primary btn-sm saved' : 'btn-primary btn-sm';
}

async function toggleSaveWord(word) {
  const saved = await isWordSaved(word);
  if (saved) {
    await unsaveWord(word);
    showToast('已取消收藏', 'info');
  } else {
    const wordData = await getWordData(word);
    await saveWord(word, wordData);
    showToast('已收藏', 'success');
  }
  updateSaveButton(word);
}

function navigateTo(page) {
  window.location.hash = page;
}

function renderHomePage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="home-page">
      <div class="card home-card">
        <h2>📖 阅读练习</h2>
        <p>选择一本英文书籍，开始沉浸式阅读</p>
        <button class="btn-primary" onclick="navigateTo('reader')">开始阅读</button>
      </div>
      <div class="card home-card">
        <h2>📚 单词本</h2>
        <p>管理和复习您收藏的单词</p>
        <button class="btn-primary" onclick="navigateTo('wordbooks')">打开单词本</button>
      </div>
      <div class="card home-card">
        <h2>✏️ 练习模式</h2>
        <p>通过练习巩固所学知识</p>
        <button class="btn-primary" onclick="navigateTo('practice')">开始练习</button>
      </div>
    </div>
  `;
}

const CATALOG_WORDBOOKS = [
  { id: 'cet4', name: '大学英语四级（CET-4）', count: '4,500', desc: '大学英语四级核心词汇' },
  { id: 'cet6', name: '大学英语六级（CET-6）', count: '6,500', desc: '大学英语六级核心词汇' },
  { id: 'kaoyan', name: '考研英语', count: '5,500', desc: '考研英语必备词汇' },
  { id: 'tem4', name: '英语专业四级（专四）', count: '8,000', desc: '英语专业四级核心词汇' },
  { id: 'tem8', name: '英语专业八级（专八）', count: '13,000', desc: '英语专业八级核心词汇' },
  { id: 'ielts', name: '雅思 IELTS', count: '8,000', desc: '雅思考试高频词汇' },
  { id: 'toefl', name: '托福 TOEFL', count: '10,000', desc: '托福考试必备词汇' },
  { id: 'gre', name: 'GRE', count: '12,000', desc: 'GRE考试核心词汇' },
  { id: 'gmat', name: 'GMAT', count: '3,500', desc: 'GMAT考试核心词汇' },
  { id: 'sat', name: 'SAT', count: '5,000', desc: 'SAT考试必备词汇' },
  { id: 'gaozhong', name: '高中英语', count: '3,500', desc: '高中英语核心词汇' },
  { id: 'chuzhong', name: '初中英语', count: '1,500', desc: '初中英语核心词汇' },
  { id: 'bec', name: 'BEC 商务英语', count: '3,000', desc: '商务英语考试词汇' },
];

function renderWordbooksPage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="wordbooks-page">
      <div class="card">
        <h2>📚 我的词书</h2>
        <p class="text-muted">创建自定义词书，添加单词或从词典书籍导入</p>
        <div id="wordbookStatus" class="status-msg"></div>
        
        <form id="createWordbookForm" class="wordbook-create-form">
          <input name="name" type="text" placeholder="词书名称，例如 我的考研词汇" required />
          <input name="description" type="text" placeholder="说明（可选）" />
          <button class="btn-primary" type="submit">创建词书</button>
        </form>
        
        <div id="myWordbookList" class="wordbook-grid"></div>
      </div>
      
      <div class="card">
        <h2>📖 词典书籍</h2>
        <p class="text-muted">从预设词典书籍导入单词到你的词书</p>
        <div class="wordbook-catalog-picker">
          <select id="catalogWordbookSelect" class="wordbook-select">
            <option value="">选择词典书籍</option>
            ${CATALOG_WORDBOOKS.map(wb => `
              <option value="${wb.id}" data-count="${wb.count}" data-desc="${wb.desc}">${wb.name}</option>
            `).join('')}
          </select>
          <button id="installCatalogBtn" class="btn-primary" type="button">导入词书</button>
        </div>
        <div id="catalogWordbookDetail" class="wordbook-catalog-detail"></div>
        <div id="catalogInstalledList" class="wordbook-catalog-installed"></div>
      </div>
    </div>
  `;
  
  setTimeout(() => {
    loadMyWordbooks();
    setupCatalogEvents();
    document.getElementById('createWordbookForm').addEventListener('submit', handleCreateWordbook);
  }, 100);
}

async function handleCreateWordbook(e) {
  e.preventDefault();
  const form = e.target;
  const name = form.name.value.trim();
  const description = form.description.value.trim();
  
  if (!name) return;
  
  try {
    await addWordbook(name, description);
    showToast('创建成功', 'success');
    form.reset();
    loadMyWordbooks();
  } catch (err) {
    showToast('创建失败: ' + err.message, 'error');
  }
}

async function loadMyWordbooks() {
  const list = document.getElementById('myWordbookList');
  if (!list) return;
  
  try {
    const wordbooks = await getWordbooks();
    
    if (wordbooks.length === 0) {
      list.innerHTML = '<div class="empty-state"><p>暂无词书</p><p>填写上方表单创建词书</p></div>';
      return;
    }
    
    list.innerHTML = wordbooks.map(wb => `
      <div class="wordbook-item-card">
        <div class="wordbook-item-card-header">
          <div class="wordbook-item-card-name">📚 ${escapeHtml(wb.name)}</div>
          <span id="wb-count-${wb.id}" class="badge">加载中...</span>
        </div>
        ${wb.description ? `<div class="wordbook-item-card-desc">${escapeHtml(wb.description)}</div>` : ''}
        <div class="wordbook-item-card-actions">
          <button class="btn-primary btn-sm" onclick="openWordbook(${wb.id})">打开</button>
          <button class="btn-danger btn-sm" onclick="deleteWordbook(${wb.id})">删除</button>
        </div>
      </div>
    `).join('');
    
    for (const wb of wordbooks) {
      const entries = await getWordbookEntries(wb.id);
      const el = document.getElementById(`wb-count-${wb.id}`);
      if (el) el.textContent = `${entries.length} 词`;
    }
  } catch (err) {
    list.innerHTML = `<div class="empty-state"><p>加载失败: ${escapeHtml(err.message)}</p></div>`;
  }
}

async function deleteWordbook(id) {
  if (!confirm('确定删除这个词书吗？')) return;
  try {
    await removeWordbook(id);
    showToast('已删除', 'success');
    loadMyWordbooks();
  } catch (err) {
    showToast('删除失败', 'error');
  }
}

function setupCatalogEvents() {
  const select = document.getElementById('catalogWordbookSelect');
  const detail = document.getElementById('catalogWordbookDetail');
  const installBtn = document.getElementById('installCatalogBtn');
  
  select.addEventListener('change', () => {
    const wb = CATALOG_WORDBOOKS.find(c => c.id === select.value);
    if (wb) {
      detail.innerHTML = `
        <div class="wordbook-catalog-info">
          <div>${wb.desc}</div>
          <div>约 ${wb.count} 个单词</div>
        </div>
      `;
    } else {
      detail.innerHTML = '';
    }
  });
  
  installBtn.addEventListener('click', async () => {
    const wb = CATALOG_WORDBOOKS.find(c => c.id === select.value);
    if (!wb) {
      showToast('请先选择词典书籍', 'error');
      return;
    }
    
    try {
      const existing = await getWordbooks();
      const hasWb = existing.some(e => e.name === wb.name);
      
      if (hasWb) {
        showToast('该词书已存在', 'warning');
        return;
      }
      
      const wordbookId = await addWordbook(wb.name, wb.desc);
      await addDemoWords(wordbookId, wb.id);
      showToast(`成功导入 "${wb.name}"`, 'success');
      loadMyWordbooks();
    } catch (err) {
      showToast('导入失败: ' + err.message, 'error');
    }
  });
}

async function loadJsonFile(filePath) {
  console.log('[MaBaonanEnglish] Loading JSON:', filePath);
  
  if (typeof AndroidDictionary !== 'undefined' && AndroidDictionary.readAssetFile) {
    try {
      console.log('[MaBaonanEnglish] Using Android API for JSON');
      const content = AndroidDictionary.readAssetFile(filePath);
      if (content) {
        console.log('[MaBaonanEnglish] JSON loaded via Android API, size:', content.length);
        const data = JSON.parse(content);
        console.log('[MaBaonanEnglish] JSON parsed, entries:', data.entries ? data.entries.length : 0);
        return data;
      } else {
        console.error('[MaBaonanEnglish] Android API returned null');
      }
    } catch (e) {
      console.error('[MaBaonanEnglish] Android API error:', e.message);
    }
  }
  
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const fullPath = `file:///android_asset/${filePath}`;
    console.log('[MaBaonanEnglish] Falling back to XHR:', fullPath);
    xhr.open('GET', fullPath, true);
    xhr.onload = () => {
      console.log('[MaBaonanEnglish] XHR status:', xhr.status);
      if (xhr.status === 200) {
        try {
          const data = JSON.parse(xhr.responseText);
          console.log('[MaBaonanEnglish] JSON loaded via XHR, entries:', data.entries ? data.entries.length : 0);
          resolve(data);
        } catch (e) {
          console.error('[MaBaonanEnglish] JSON parse error:', e.message);
          reject(new Error(`JSON parse error: ${e.message}`));
        }
      } else {
        console.error('[MaBaonanEnglish] XHR failed:', xhr.status);
        reject(new Error(`HTTP error: ${xhr.status}`));
      }
    };
    xhr.onerror = () => {
      console.error('[MaBaonanEnglish] XHR network error');
      reject(new Error('Network error'));
    };
    xhr.ontimeout = () => {
      console.error('[MaBaonanEnglish] XHR timeout');
      reject(new Error('Timeout'));
    };
    xhr.timeout = 10000;
    xhr.send();
  });
}

async function addDemoWords(wordbookId, catalogId) {
  const fileName = `${catalogId}_kylebing.json`;
  
  const paths = [
    `wordbooks/${fileName}`,
    `./wordbooks/${fileName}`,
  ];
  
  let data = null;
  
  for (const filePath of paths) {
    try {
      data = await loadJsonFile(filePath);
      break;
    } catch (e) {
      console.log(`Load failed for ${filePath}:`, e.message);
    }
  }
  
  if (!data) {
    throw new Error('无法加载词书数据，请检查文件路径');
  }
  
  const entries = data.entries || [];
  
  showToast(`正在导入 ${entries.length} 个单词...`, 'info');
  
  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];
    await addWordbookEntry(
      wordbookId,
      entry.word,
      entry.pronunciation || '',
      entry.translation || '',
      entry.example || ''
    );
    
    if ((i + 1) % 500 === 0 || i === entries.length - 1) {
      showToast(`已导入 ${i + 1}/${entries.length} 个单词`, 'info');
    }
  }
  
  showToast(`成功导入 ${entries.length} 个单词`, 'success');
}

let currentWordbookId = null;
let currentWordbookEntries = [];
let currentWordbookPage = 0;
const WORDS_PER_PAGE = 20;

async function openWordbook(id) {
  currentWordbookId = id;
  currentWordbookPage = 0;
  
  const wordbook = await getWordbook(id);
  currentWordbookEntries = await getWordbookEntries(id);
  
  const content = document.getElementById('pageContent');
  const totalPages = Math.max(1, Math.ceil(currentWordbookEntries.length / WORDS_PER_PAGE));
  
  content.innerHTML = `
    <div class="wordbook-detail-page">
      <div class="card">
        <div class="wordbook-editor-head">
          <div>
            <h2 id="activeWordbookTitle">${escapeHtml(wordbook?.name || '词书')}</h2>
            <p id="activeWordbookMeta" class="text-muted">${currentWordbookEntries.length} 个单词</p>
          </div>
          <div class="wordbook-editor-actions">
            <button class="btn-secondary btn-sm" onclick="renderWordbooksPage()">← 返回</button>
          </div>
        </div>
        
        <div class="wordbook-add-panel">
          <label class="wordbook-add-label" for="addWordInput">添加单词</label>
          <div class="wordbook-add-row">
            <input id="addWordInput" type="text" placeholder="输入单词，例如 forever" autocomplete="off" />
            <button class="btn-primary" onclick="addWordToBook(${id})">添加</button>
          </div>
          <div id="wordPreview" class="wordbook-word-preview" hidden></div>
        </div>
        
        <div class="wordbook-import-panel">
          <label class="wordbook-add-label" for="importFileInput">批量导入</label>
          <div class="wordbook-import-row">
            <input id="importFileInput" type="file" accept=".txt,.csv" />
            <button class="btn-secondary" onclick="importWordsToBook(${id})">开始导入</button>
          </div>
          <p class="text-muted" style="font-size:12px;margin-top:8px">支持 txt / csv，每行一个单词或「单词,中文,音标」格式</p>
        </div>
        
        <div id="wordbookEntries"></div>
        
        <div id="wordbookPagination" class="wordbook-pagination">
          <button class="btn-secondary btn-sm" onclick="changeWordbookPage(${id}, ${currentWordbookPage - 1})" ${currentWordbookPage === 0 ? 'disabled' : ''}>← 上一页</button>
          <span class="wordbook-page-info">第 ${currentWordbookPage + 1} / ${totalPages} 页</span>
          <button class="btn-secondary btn-sm" onclick="changeWordbookPage(${id}, ${currentWordbookPage + 1})" ${currentWordbookPage >= totalPages - 1 ? 'disabled' : ''}>下一页 →</button>
        </div>
      </div>
    </div>
  `;
  
  renderWordbookEntries(id, currentWordbookEntries, currentWordbookPage);
}

async function changeWordbookPage(wordbookId, page) {
  const totalPages = Math.max(1, Math.ceil(currentWordbookEntries.length / WORDS_PER_PAGE));
  if (page < 0 || page >= totalPages) return;
  
  currentWordbookPage = page;
  await openWordbook(wordbookId);
}

async function renderWordbookEntries(wordbookId, entries, page = 0) {
  const container = document.getElementById('wordbookEntries');
  if (!container) return;
  
  const start = page * WORDS_PER_PAGE;
  const end = start + WORDS_PER_PAGE;
  const pageEntries = entries.slice(start, end);
  
  if (entries.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>暂无单词</p><p>在上方输入框添加单词</p></div>';
    return;
  }
  
  const savedWords = await getSavedWords();
  const savedWordSet = new Set(savedWords.map(w => w.word.toLowerCase()));
  
  container.innerHTML = pageEntries.map((entry, index) => {
    const isSaved = savedWordSet.has(entry.word.toLowerCase());
    return `
    <article class="wordbook-entry-card">
      <div class="wordbook-entry-content">
        <div class="wordbook-entry-head">
          <div class="wordbook-entry-title">
            <div class="wordbook-entry-wordline">
              <div class="wordbook-entry-word">${escapeHtml(entry.word)}</div>
            </div>
            ${entry.pronunciation ? `<div class="wordbook-entry-phonetic">${formatPhonetic(entry.pronunciation)}</div>` : ''}
          </div>
          <div class="wordbook-entry-badges">
            <button class="wordbook-speak-btn" onclick="speakWord('${escapeHtml(entry.word)}')" title="发音">🔊</button>
            <button class="wordbook-fav-btn ${isSaved ? 'saved' : ''}" onclick="toggleWordbookFavorite('${escapeHtml(entry.word)}', ${entry.id})" title="${isSaved ? '取消收藏' : '收藏'}">
              ${isSaved ? '★' : '☆'}
            </button>
            <button class="wordbook-delete-btn" onclick="removeWordFromBook(${wordbookId}, ${entry.id})" title="删除">🗑</button>
          </div>
        </div>
        <div class="wordbook-entry-translation">${escapeHtml(entry.translation || '暂无释义')}</div>
        ${entry.example ? `<div class="wordbook-entry-example">${escapeHtml(entry.example)}</div>` : ''}
      </div>
    </article>
  `}).join('');
}

async function toggleWordbookFavorite(word, entryId) {
  const isSaved = await isWordSaved(word);
  if (isSaved) {
    await unsaveWord(word);
    showToast('已取消收藏', 'info');
  } else {
    await saveWord(word, {
      word: word,
      pronunciation: '',
      translation: '',
      example: ''
    });
    showToast('已收藏', 'success');
  }
  
  if (currentWordbookId) {
    currentWordbookEntries = await getWordbookEntries(currentWordbookId);
    await renderWordbookEntries(currentWordbookId, currentWordbookEntries, currentWordbookPage);
  }
}

async function addWordToBook(wordbookId) {
  const input = document.getElementById('addWordInput');
  const word = input.value.trim();
  
  if (!word) {
    showToast('请输入单词', 'error');
    return;
  }
  
  try {
    let data = { word };
    try {
      const wordData = await getWordData(word);
      if (wordData) {
        data.pronunciation = wordData.pronunciation;
        data.translation = wordData.translation;
        data.example = wordData.example;
      }
    } catch (err) {
      console.log('Auto lookup failed, using basic entry');
    }
    
    await addWordbookEntry(wordbookId, data.word, data.pronunciation, data.translation, data.example);
    showToast(`已添加 "${word}"`, 'success');
    input.value = '';
    
    const entries = await getWordbookEntries(wordbookId);
    renderWordbookEntries(wordbookId, entries);
  } catch (err) {
    showToast('添加失败: ' + err.message, 'error');
  }
}

async function removeWordFromBook(wordbookId, entryId) {
  try {
    await removeWordbookEntry(entryId);
    const entries = await getWordbookEntries(wordbookId);
    renderWordbookEntries(wordbookId, entries);
    showToast('已删除', 'success');
  } catch (err) {
    showToast('删除失败', 'error');
  }
}

async function importWordsToBook(wordbookId) {
  const fileInput = document.getElementById('importFileInput');
  const file = fileInput.files[0];
  
  if (!file) {
    showToast('请选择文件', 'error');
    return;
  }
  
  try {
    const text = await file.text();
    const lines = text.split('\n').filter(l => l.trim());
    let successCount = 0;
    
    for (const line of lines) {
      const parts = line.split(/[,，\t]/).map(p => p.trim());
      const word = parts[0];
      const translation = parts[1] || '';
      const pronunciation = parts[2] || '';
      
      if (word) {
        try {
          await addWordbookEntry(wordbookId, word, pronunciation, translation);
          successCount++;
        } catch (err) {
          console.log('Failed to add:', word, err.message);
        }
      }
    }
    
    showToast(`成功导入 ${successCount} 个单词`, 'success');
    const entries = await getWordbookEntries(wordbookId);
    renderWordbookEntries(wordbookId, entries);
  } catch (err) {
    showToast('导入失败: ' + err.message, 'error');
  }
}

const BOOK_CHAPTERS = {};

const PRESET_BOOKS = [
  { id: 'alice-wonderland', title: "Alice's Adventures in Wonderland", author: 'Lewis Carroll', words: '27,000', desc: '爱丽丝梦游仙境', chapters: 12 },
  { id: 'time-machine', title: 'The Time Machine', author: 'H.G. Wells', words: '32,000', desc: '时间机器', chapters: 17 },
  { id: 'pride-prejudice', title: 'Pride and Prejudice', author: 'Jane Austen', words: '121,000', desc: '傲慢与偏见', chapters: 61 },
  { id: 'frankenstein', title: 'Frankenstein', author: 'Mary Shelley', words: '75,000', desc: '弗兰肯斯坦', chapters: 48 },
  { id: 'great-expectations', title: 'Great Expectations', author: 'Charles Dickens', words: '183,000', desc: '远大前程', chapters: 59 },
  { id: 'andersen-fairy-tales', title: "Hans Andersen's Fairy Tales", author: 'Hans Christian Andersen', words: '100,000', desc: '安徒生童话精选', chapters: 20 },
  { id: 'andersen-fairy-tales-complete', title: "Hans Andersen's Fairy Tales (Complete)", author: 'Hans Christian Andersen', words: '500,000', desc: '安徒生童话全集', chapters: 156 },
  { id: 'grimms-fairy-tales', title: "Grimm's Fairy Tales", author: 'Brothers Grimm', words: '50,000', desc: '格林童话', chapters: 5 },
];

let currentBookId = null;
let currentChapterIndex = 0;

function renderReaderPage() {
  console.log('=== renderReaderPage called ===');
  const content = document.getElementById('pageContent');
  console.log('pageContent:', !!content);
  
  content.innerHTML = `
    <div class="reader-page">
      <div class="card">
        <h2>📖 阅读器</h2>
        <p class="text-muted">选择书籍阅读，或导入自己的小说</p>
        
        <div class="reading-input-tabs">
          <button class="tab-btn active" onclick="switchReadingTab('upload')">📁 导入文件</button>
          <button class="tab-btn" onclick="switchReadingTab('paste')">📝 快速粘贴</button>
        </div>
        
        <div id="pastePanel" class="reading-tab-panel hidden">
          <input id="readingTitle" placeholder="标题（可选）" class="reading-title-input" />
          <textarea id="readingContent" placeholder="粘贴英文书籍、文档或短故事..." rows="6"></textarea>
          <button class="btn-primary" onclick="createReadingFromPaste()">开始阅读</button>
        </div>
        
        <div id="uploadPanel" class="reading-tab-panel">
          <input id="uploadTitle" placeholder="标题（可选，默认用文件名）" class="reading-title-input" />
          <div id="uploadZone" class="upload-zone">
            <div>📄 点击选择文件</div>
            <div style="font-size:12px;margin-top:8px;color:var(--muted)">支持 TXT · MD 格式</div>
            <input id="fileInput" type="file" accept=".txt,.md,.text" />
          </div>
          <div id="uploadFileName" class="upload-meta"></div>
          <button class="btn-primary" onclick="uploadReadingFile()">上传并开始</button>
        </div>
      </div>
      
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2>📚 精选书库</h2>
          <span class="badge">${PRESET_BOOKS.length}本</span>
        </div>
        <div id="presetBookList"></div>
      </div>
      
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <h2>📖 我的导入</h2>
          <span id="readingListCount" class="badge">0</span>
        </div>
        <div id="readingList"></div>
      </div>
    </div>
  `;
  
  setTimeout(() => {
    loadPresetBooks();
    loadReadingList();
    setupFileInput();
  }, 100);
}

function switchReadingTab(tab) {
  document.querySelectorAll('.reading-input-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.reading-input-tabs .tab-btn[onclick="switchReadingTab('${tab}')"]`)?.classList.add('active');
  document.getElementById('pastePanel').classList.toggle('hidden', tab !== 'paste');
  document.getElementById('uploadPanel').classList.toggle('hidden', tab !== 'upload');
}

function setupFileInput() {
  const uploadZone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  const uploadFileName = document.getElementById('uploadFileName');
  
  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) {
        uploadFileName.textContent = fileInput.files[0].name;
      } else {
        uploadFileName.textContent = '';
      }
    });
  }
}

async function createReadingFromPaste() {
  const title = document.getElementById('readingTitle').value.trim() || 'Untitled';
  const content = document.getElementById('readingContent').value.trim();
  
  if (!content) {
    showToast('请输入内容', 'error');
    return;
  }
  
  try {
    const docId = await addReadingDocument(title, content);
    showToast('创建成功', 'success');
    openReadingDocument(docId);
  } catch (e) {
    showToast('创建失败: ' + e.message, 'error');
  }
}

async function uploadReadingFile() {
  const fileInput = document.getElementById('fileInput');
  const title = document.getElementById('uploadTitle').value.trim();
  const file = fileInput.files[0];
  
  if (!file) {
    showToast('请选择文件', 'error');
    return;
  }
  
  try {
    const text = await file.text();
    const docTitle = title || file.name.replace(/\.[^/.]+$/, '');
    const docId = await addReadingDocument(docTitle, text);
    showToast('上传成功', 'success');
    openReadingDocument(docId);
  } catch (e) {
    showToast('上传失败: ' + e.message, 'error');
  }
}

function loadPresetBooks() {
  const list = document.getElementById('presetBookList');
  if (!list) return;
  
  list.innerHTML = PRESET_BOOKS.map(book => `
    <div class="book-item" onclick="openPresetBook('${book.id}')">
      <div class="book-item-title">${escapeHtml(book.title)}</div>
      <div class="book-item-meta">${escapeHtml(book.author)} · ${book.words} 词</div>
      <div class="book-item-desc">${escapeHtml(book.desc)}</div>
    </div>
  `).join('');
}

async function loadReadingList() {
  const list = document.getElementById('readingList');
  const count = document.getElementById('readingListCount');
  if (!list || !count) return;
  
  try {
    const docs = await getReadingDocuments();
    count.textContent = docs.length;
    
    if (docs.length === 0) {
      list.innerHTML = '<div class="empty-state"><p>还没有导入书籍</p><p>点击上方「导入文件」或「快速粘贴」添加</p></div>';
      return;
    }
    
    list.innerHTML = docs.map(doc => `
      <div class="reading-book-card">
        <div class="reading-book-card-header">
          <div class="reading-book-cover">📘</div>
          <div class="reading-book-headcopy">
            <div class="reading-book-title">${escapeHtml(doc.title)}</div>
            <div class="reading-book-meta">
              <span class="reading-book-chip">${doc.block_count || 0} 段</span>
              <span class="reading-book-chip">${doc.read_progress || 0}%</span>
            </div>
          </div>
        </div>
        <div class="reading-book-body">
          ${doc.read_progress > 0 ? `
            <div class="reading-book-progress-wrap">
              <div class="reading-book-progress-label">
                <span>阅读进度</span>
                <span>${doc.read_progress}%</span>
              </div>
              <div class="reading-book-progress">
                <div class="reading-book-progress-fill" style="width:${doc.read_progress}%"></div>
              </div>
            </div>
          ` : ''}
        </div>
        <div class="reading-book-foot">
          <div class="reading-book-actions">
            <button class="btn-primary btn-sm" onclick="openReadingDocument(${doc.id})">${doc.read_progress > 0 ? '继续阅读' : '开始阅读'}</button>
            <button class="btn-danger btn-sm" onclick="deleteReadingDoc(${doc.id})">删除</button>
          </div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><p>加载失败: ${escapeHtml(e.message)}</p></div>`;
  }
}

async function deleteReadingDoc(id) {
  if (!confirm('确定删除这本书吗？')) return;
  try {
    await deleteReadingDocument(id);
    await loadReadingList();
    showToast('已删除', 'success');
  } catch (e) {
    showToast('删除失败', 'error');
  }
}

async function openPresetBook(bookId) {
  const book = PRESET_BOOKS.find(b => b.id === bookId);
  if (!book) return;
  
  currentBookId = bookId;
  currentChapterIndex = 0;
  
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="reading-view">
      <div class="reader-topbar">
        <div class="reader-topbar-inner">
          <button class="btn-secondary" onclick="renderReaderPage()">← 返回</button>
          <div class="reader-topbar-title">${escapeHtml(book.title)}</div>
          <div class="reader-topbar-actions">
            <button class="btn-secondary btn-sm" onclick="showChapterList()">📋</button>
          </div>
        </div>
      </div>
      <div class="chapter-list-container">
        <div class="chapter-list-header">
          <h3>${escapeHtml(book.title)}</h3>
          <p>正在加载章节...</p>
        </div>
        <div class="chapter-list">
          <div class="loading-state">📚 正在加载书籍内容，请稍候...</div>
        </div>
      </div>
    </div>
  `;
  
  try {
    const chapters = await window.loadBookChapters(bookId);
    BOOK_CHAPTERS[bookId] = chapters;
    
    const chapterList = document.querySelector('.chapter-list');
    const chapterHeader = document.querySelector('.chapter-list-header p');
    
    if (chapterHeader) {
      chapterHeader.textContent = `${escapeHtml(book.author)} · ${chapters.length} 章`;
    }
    
    if (chapterList) {
      chapterList.innerHTML = chapters.map((chapter, index) => `
        <div class="chapter-item" onclick="openChapter(${index})">
          <div class="chapter-number">${index + 1}</div>
          <div class="chapter-info">
            <div class="chapter-title">${escapeHtml(chapter.title)}</div>
          </div>
          <div class="chapter-arrow">→</div>
        </div>
      `).join('');
    }
    
    if (chapters.length > 0) {
      openChapter(0);
    }
  } catch (e) {
    showToast('加载书籍失败: ' + e.message, 'error');
    console.error('Failed to load book:', e);
  }
}

function showChapterList() {
  const book = PRESET_BOOKS.find(b => b.id === currentBookId);
  if (!book) return;
  
  const chapters = BOOK_CHAPTERS[currentBookId] || [];
  
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="reading-view">
      <div class="reader-topbar">
        <div class="reader-topbar-inner">
          <button class="btn-secondary" onclick="openChapter(currentChapterIndex)">← 返回阅读</button>
          <div class="reader-topbar-title">章节列表</div>
          <div class="reader-topbar-actions"></div>
        </div>
      </div>
      <div class="chapter-list-container">
        <div class="chapter-list-header">
          <h3>${escapeHtml(book.title)}</h3>
          <p>${escapeHtml(book.author)} · ${chapters.length} 章</p>
        </div>
        <div class="chapter-list">
          ${chapters.map((chapter, index) => `
            <div class="chapter-item ${index === currentChapterIndex ? 'active' : ''}" onclick="openChapter(${index})">
              <div class="chapter-number">${index + 1}</div>
              <div class="chapter-info">
                <div class="chapter-title">${escapeHtml(chapter.title)}</div>
              </div>
              <div class="chapter-arrow">→</div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

let currentReadingMode = 'bilingual';
let currentTranslationQueue = null;
let currentBookTranslationManager = null;
let currentChapterPages = [];
let currentPageIndex = 0;
const CHARS_PER_PAGE = 700;

function splitChapterIntoPages(content, charsPerPage = CHARS_PER_PAGE) {
  const paragraphs = splitIntoParagraphs(content);
  const pages = [];
  let currentPage = [];
  let currentLength = 0;

  for (const para of paragraphs) {
    currentPage.push(para);
    currentLength += para.length;
    if (currentLength >= charsPerPage) {
      pages.push(currentPage);
      currentPage = [];
      currentLength = 0;
    }
  }

  if (currentPage.length > 0) {
    pages.push(currentPage);
  }

  return pages.length > 0 ? pages : [[]];
}

function renderPage(pageParagraphs, pageIndex, totalPages, chapterIndex) {
  const paragraphsHtml = pageParagraphs.map((para, i) => {
    const globalParaIndex = currentPageIndex * 100 + i;
    return `
      <div class="bilingual-block" id="paragraph-${globalParaIndex}">
        <div class="bilingual-en">${wrapWordsInParagraph(para.replace(/\n/g, '<br>'))}</div>
        <div class="bilingual-zh loading" id="paragraph-${globalParaIndex}-zh">
          <span class="loading-dots">翻译中...</span>
        </div>
      </div>
    `;
  }).join('');

  return `
    <div class="page-container">
      <div class="page-content">${paragraphsHtml}</div>
      <div class="page-nav">
        <button class="btn-secondary ${currentPageIndex === 0 ? 'disabled' : ''}"
          onclick="goToPage(${currentPageIndex - 1})">← 上一页</button>
        <span class="page-info">${currentPageIndex + 1} / ${totalPages}</span>
        <button class="btn-secondary ${currentPageIndex === totalPages - 1 ? 'disabled' : ''}"
          onclick="goToPage(${currentPageIndex + 1})">下一页 →</button>
      </div>
    </div>
  `;
}

function goToPage(pageIndex) {
  if (pageIndex < 0 || pageIndex >= currentChapterPages.length) return;
  currentPageIndex = pageIndex;
  renderCurrentPage();
  document.getElementById('readerPaper').scrollTop = 0;
}

function renderCurrentPage() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;

  const pages = currentChapterPages;
  const page = pages[currentPageIndex] || [];

  if (currentReadingMode === 'en') {
    paper.innerHTML = page.map(para =>
      `<div class="bilingual-block"><div class="bilingual-en">${wrapWordsInParagraph(para.replace(/\n/g, '<br>'))}</div></div>`
    ).join('') + renderPageNav();
  } else if (currentReadingMode === 'zh') {
    paper.innerHTML = page.map((para, i) => {
      const globalParaIndex = currentPageIndex * 100 + i;
      return `
        <div class="bilingual-block" id="paragraph-${globalParaIndex}">
          <div class="bilingual-en" style="display:none">${wrapWordsInParagraph(para.replace(/\n/g, '<br>'))}</div>
          <div class="bilingual-zh loading" id="paragraph-${globalParaIndex}-zh">
            <span class="loading-dots">加载中...</span>
          </div>
        </div>
      `;
    }).join('') + renderPageNav();
    translateCurrentPage();
  } else if (currentReadingMode === 'on-demand') {
    paper.innerHTML = page.map((para, i) => {
      const globalParaIndex = currentPageIndex * 100 + i;
      return `
        <div class="bilingual-block" id="paragraph-${globalParaIndex}">
          <div class="bilingual-en">${wrapWordsInParagraph(para.replace(/\n/g, '<br>'))}</div>
          <div class="bilingual-zh on-demand" id="paragraph-${globalParaIndex}-zh"
               onclick="translateOnDemand(${globalParaIndex}, this)">
            <span class="translate-hint">点击翻译</span>
          </div>
        </div>
      `;
    }).join('') + renderPageNav();
  } else {
    paper.innerHTML = page.map((para, i) => {
      const globalParaIndex = currentPageIndex * 100 + i;
      return `
        <div class="bilingual-block" id="paragraph-${globalParaIndex}">
          <div class="bilingual-en">${wrapWordsInParagraph(para.replace(/\n/g, '<br>'))}</div>
          <div class="bilingual-zh loading" id="paragraph-${globalParaIndex}-zh">
            <span class="loading-dots">翻译中...</span>
          </div>
        </div>
      `;
    }).join('') + renderPageNav();
  }

  setupWordClick();

  if (currentReadingMode === 'bilingual') {
    translateCurrentPage();
  }
}

function renderPageNav() {
  const totalPages = currentChapterPages.length;
  return `
    <div class="page-nav">
      <button class="btn-secondary ${currentPageIndex === 0 ? 'disabled' : ''}"
        onclick="goToPage(${currentPageIndex - 1})">← 上一页</button>
      <span class="page-info">第${currentPageIndex + 1}/${totalPages}页</span>
      <button class="btn-secondary ${currentPageIndex === totalPages - 1 ? 'disabled' : ''}"
        onclick="goToPage(${currentPageIndex + 1})">下一页 →</button>
    </div>
  `;
}

async function translateCurrentPage() {
  const page = currentChapterPages[currentPageIndex] || [];
  for (let i = 0; i < page.length; i++) {
    const globalParaIndex = currentPageIndex * 100 + i;
    const trimmed = page[i].trim();
    const cached = await getCachedTranslation(trimmed);
    if (cached !== null && cached !== '') {
      const zhEl = document.getElementById(`paragraph-${globalParaIndex}-zh`);
      if (zhEl) {
        zhEl.classList.remove('loading');
        zhEl.classList.add('zh-fade-in');
        zhEl.innerHTML = cached;
      }
    }
  }
}

function translateOnDemand(globalParaIndex, el) {
  el.classList.remove('on-demand');
  el.classList.add('loading');
  el.innerHTML = '<span class="loading-dots">翻译中...</span>';
  el.onclick = null;

  const page = currentChapterPages[currentPageIndex] || [];
  const localIndex = globalParaIndex % 100;
  const text = page[localIndex];

  translateParagraph(text).then(translation => {
    el.classList.remove('loading');
    el.classList.add('zh-fade-in');
    el.innerHTML = translation || '<span class="no-translation">暂无翻译</span>';
  });
}

function updateTranslationProgress(progress) {
  const bar = document.getElementById('translationProgressBar');
  const text = document.getElementById('translationProgressText');
  const container = document.getElementById('translationProgressContainer');

  if (!container) return;

  if (progress.status === 'done') {
    container.style.display = 'none';
    return;
  }

  container.style.display = 'flex';
  if (bar) {
    bar.style.width = progress.bookPercent + '%';
    bar.className = progress.bookPercent >= 100 ? 'translation-progress-bar done' : 'translation-progress-bar';
  }
  if (text) {
    const timeStr = progress.estimatedTime > 0 ? ` 预计${progress.estimatedTime}秒` : '';
    text.textContent = `第${progress.currentChapter}/${progress.totalChapters}章 ${progress.completedParagraphs}/${progress.totalParagraphs}段 ${progress.bookPercent}%${timeStr}`;
  }
}

function pauseTranslation() {
  if (currentBookTranslationManager) {
    currentBookTranslationManager.pause();
    const btn = document.getElementById('translationPauseBtn');
    if (btn) {
      btn.textContent = '继续';
      btn.onclick = resumeTranslation;
    }
  }
}

function resumeTranslation() {
  if (currentBookTranslationManager) {
    currentBookTranslationManager.resume();
    const btn = document.getElementById('translationPauseBtn');
    if (btn) {
      btn.textContent = '暂停';
      btn.onclick = pauseTranslation;
    }
  }
}

function cancelTranslation() {
  if (currentBookTranslationManager) {
    currentBookTranslationManager.cancel();
    const container = document.getElementById('translationProgressContainer');
    if (container) container.style.display = 'none';
  }
}

function setReadingMode(mode) {
  currentReadingMode = mode;
  const paper = document.getElementById('readerPaper');
  if (!paper) return;

  paper.classList.remove('mode-en', 'mode-bilingual', 'mode-ondemand', 'mode-zh');
  if (mode === 'en') {
    paper.classList.add('mode-en');
  } else if (mode === 'zh') {
    paper.classList.add('mode-zh');
  } else if (mode === 'bilingual') {
    paper.classList.add('mode-bilingual');
  } else if (mode === 'on-demand') {
    paper.classList.add('mode-ondemand');
  }

  const selector = document.getElementById('readingModeSelector');
  if (selector) selector.value = mode;

  if (mode === 'bilingual' && currentTranslationQueue) {
    currentTranslationQueue.resume();
  }

  if (mode === 'zh' || mode === 'bilingual') {
    translateCurrentPage();
  }
}

function openChapter(chapterIndex) {
  const book = PRESET_BOOKS.find(b => b.id === currentBookId);
  if (!book) return;

  const chapters = BOOK_CHAPTERS[currentBookId] || [];
  if (chapterIndex < 0 || chapterIndex >= chapters.length) return;

  currentChapterIndex = chapterIndex;
  currentPageIndex = 0;
  const chapter = chapters[chapterIndex];

  if (typeof setActiveChapterIndex === 'function') {
    setActiveChapterIndex(chapterIndex);
  }

  currentChapterPages = splitChapterIntoPages(chapter.content);

  const chapterOptions = chapters.map((ch, i) =>
    `<option value="${i}" ${i === chapterIndex ? 'selected' : ''}>第${i + 1}章 ${escapeHtml(ch.title)}</option>`
  ).join('');

  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="reading-view">
      <div class="reader-topbar">
        <div class="reader-topbar-inner">
          <select id="chapterSelector" class="chapter-selector" onchange="openChapter(parseInt(this.value))">
            ${chapterOptions}
          </select>
          <div class="reader-topbar-actions">
            <select id="readingModeSelector" class="reading-mode-selector" onchange="setReadingMode(this.value)">
              <option value="en" ${currentReadingMode === 'en' ? 'selected' : ''}>英文</option>
              <option value="zh" ${currentReadingMode === 'zh' ? 'selected' : ''}>中文</option>
              <option value="bilingual" ${currentReadingMode === 'bilingual' ? 'selected' : ''}>双语</option>
            </select>
            <button class="btn-secondary btn-sm" onclick="speakPage()">🔊</button>
          </div>
        </div>
      </div>
      <div class="reader-paper mode-${currentReadingMode === 'en' ? 'en' : currentReadingMode === 'bilingual' ? 'bilingual' : 'ondemand'}" id="readerPaper"></div>
      <div class="translation-progress-container" id="translationProgressContainer" style="display:none">
        <div class="translation-progress-info">
          <span class="translation-progress-text" id="translationProgressText">0/0段 0%</span>
          <div class="translation-progress-actions">
            <button class="translation-progress-btn" id="translationPauseBtn" onclick="pauseTranslation()">暂停</button>
            <button class="translation-progress-btn" onclick="cancelTranslation()">取消</button>
          </div>
        </div>
        <div class="translation-progress-track">
          <div class="translation-progress-bar" id="translationProgressBar" style="width:0%"></div>
        </div>
      </div>
      <div class="reader-footer">
        <button class="btn-secondary ${chapterIndex === 0 ? 'disabled' : ''}" onclick="openChapter(${chapterIndex - 1})">
          ← 上一章
        </button>
        <div class="reader-progress">
          <span>${chapterIndex + 1} / ${chapters.length}</span>
        </div>
        <button class="btn-secondary ${chapterIndex === chapters.length - 1 ? 'disabled' : ''}" onclick="openChapter(${chapterIndex + 1})">
          下一章 →
        </button>
      </div>
    </div>
  `;

  setTimeout(() => {
    renderCurrentPage();

    if (currentReadingMode === 'bilingual' && typeof startBookTranslation !== 'undefined') {
      if (!currentBookTranslationManager || currentBookTranslationManager.bookId !== currentBookId) {
        currentBookTranslationManager = startBookTranslation(currentBookId, chapters, updateTranslationProgress);
      } else if (typeof setActiveChapterIndex === 'function') {
        setActiveChapterIndex(chapterIndex);
      }
    }

    if (typeof preloadChapterWords === 'function') {
      preloadChapterWords(chapter.content);
    }
  }, 100);
}

async function loadCachedTranslationsForCurrentChapter(chapterContent) {
  const paragraphs = splitIntoParagraphs(chapterContent);
  for (let i = 0; i < paragraphs.length; i++) {
    const trimmed = paragraphs[i].trim();
    const cached = await getCachedTranslation(trimmed);
    if (cached !== null && cached !== '') {
      const zhEl = document.getElementById(`paragraph-${i}-zh`);
      if (zhEl) {
        zhEl.classList.remove('loading', 'on-demand');
        zhEl.classList.add('zh-fade-in');
        zhEl.innerHTML = cached;
      }
    }
  }
}

async function openReadingDocument(docId) {
  try {
    const doc = await getReadingDocument(docId);
    if (!doc) {
      showToast('文档不存在', 'error');
      return;
    }
    
    const content = document.getElementById('pageContent');
    content.innerHTML = `
      <div class="reading-view">
        <div class="reader-topbar">
          <div class="reader-topbar-inner">
            <button class="btn-secondary" onclick="renderReaderPage()">← 返回</button>
            <div class="reader-topbar-title">${escapeHtml(doc.title)}</div>
            <div class="reader-topbar-actions">
              <button class="btn-secondary btn-sm" onclick="speakPage()">🔊</button>
            </div>
          </div>
        </div>
        <div class="reader-paper" id="readerPaper"></div>
      </div>
    `;
    
    setTimeout(() => loadDocumentContent(doc), 100);
  } catch (e) {
    showToast('打开失败: ' + e.message, 'error');
  }
}

function loadPresetBookContent(bookId) {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  const contents = {
    demo1: `
      <div class="reading-block">
        <div class="reading-text-en">Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it, 'and what is the use of a book,' thought Alice 'without pictures or conversations?'</div>
        <div class="reading-text-zh">爱丽丝开始厌倦了坐在姐姐身边的河岸上，无所事事。有一两次她偷偷看了看姐姐正在读的书，但书里没有图画或对话。"一本书没有图画或对话有什么用呢？"爱丽丝想。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">So she was considering in her own mind (as well as she could, for the hot day made her feel very sleepy and stupid), whether the pleasure of making a daisy-chain would be worth the trouble of getting up and picking the daisies, when suddenly a White Rabbit with pink eyes ran close by her.</div>
        <div class="reading-text-zh">于是她正在心里盘算着（天气太热，她感到昏昏欲睡），做一个雏菊花环的乐趣是否值得她站起来去摘雏菊的麻烦，这时突然一只长着粉红色眼睛的白兔从她身边跑过。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">There was nothing so very remarkable in that; nor did Alice think it so very much out of the way to hear the Rabbit say to itself, 'Oh dear! Oh dear! I shall be late!' (when she thought it over afterwards, it occurred to her that she ought to have wondered at this, but at the time it all seemed quite natural); but when the Rabbit actually took a watch out of its waistcoat-pocket, and looked at it, and then hurried on, Alice started to her feet, for it flashed across her mind that she had never before seen a rabbit with either a waistcoat-pocket, or a watch to take out of it, and burning with curiosity, she ran across the field after it, and fortunately was just in time to see it pop down a large rabbit-hole under the hedge.</div>
        <div class="reading-text-zh">这没什么特别了不起的；爱丽丝也不觉得听到兔子自言自语有什么奇怪的，"哦，天哪！哦，天哪！我要迟到了！"（后来她回想起来，觉得自己本应该对此感到惊奇，但当时一切都显得很自然）；但是当兔子真的从背心口袋里掏出一块表看了看，然后匆匆赶路时，爱丽丝猛地站了起来，因为她突然想到，她以前从未见过一只兔子既有背心口袋，又有表可以掏出来，于是她好奇得不得了，穿过田野追了过去，幸运的是，她及时看到它钻进了树篱下的一个大兔子洞。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">In another moment down went Alice after it, never once considering how in the world she was to get out again. The rabbit-hole went straight on like a tunnel for some way, and then dipped suddenly down, so suddenly that Alice had not a moment to think about stopping herself before she found herself falling down a very deep well.</div>
        <div class="reading-text-zh">爱丽丝立刻跟着它跳了下去，根本没考虑怎么再爬上来。兔子洞像隧道一样笔直地延伸了一段，然后突然向下倾斜，倾斜得如此突然，爱丽丝还没来得及想怎么停下来，就发现自己掉进了一口很深的井里。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Either the well was very deep, or she fell very slowly, for she had plenty of time as she went down to look about her and to wonder what was going to happen next. First, she tried to look down and make out what she was coming to, but it was too dark to see anything; then she looked at the sides of the well, and noticed that they were filled with cupboards and book-shelves; here and there she saw maps and pictures hung upon pegs.</div>
        <div class="reading-text-zh">也许是井太深了，或者她下落得太慢了，因为她有足够的时间四处张望，想知道接下来会发生什么。起初，她试图向下看，看看自己要落到什么地方，但太黑了什么也看不见；然后她看了看井壁，发现上面摆满了柜子和书架，到处都挂着地图和图画。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Down, down, down. Would the fall never come to an end? 'I wonder how many miles I've fallen by this time?' she said aloud. 'I must be getting somewhere near the centre of the earth. Let me see: that would be four thousand miles down, I think.' (for, you see, Alice had learned several things of this sort in her lessons in the schoolroom, and though this was not a very good opportunity for showing off her knowledge, as there was no one to listen to her, still it was good practice to say it over).</div>
        <div class="reading-text-zh">向下，向下，向下。这跌落什么时候才会结束？"我想知道我现在已经下落了多少英里？"她大声说。"我一定快到地心了。让我想想：我想那应该是四千英里深。"（你知道的，爱丽丝在学校的课堂上学过一些这类知识，虽然这不是炫耀她知识的好机会，因为没人听她说话，但把它说出来总是好的练习）。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Presently she began again. 'I wonder if I shall fall right through the earth! How funny it'll seem to come out among the people that walk with their heads downward! The antipathies, I think--' (she was rather glad there was no one listening, this time, as it didn't sound at all the right word) '--but I shall have to ask them what the name of the country is, you know. Please, Ma'am, is this New Zealand or Australia?' (and she tried to curtsey as she spoke--fancy curtseying as you're falling through the air! Do you think you could manage it?)</div>
        <div class="reading-text-zh">过了一会儿，她又开始说话了。"我想知道我会不会从地球的另一边掉出来！头朝下走路的人们看起来会多么有趣啊！我想那是对跖点——"（这次她很高兴没人听，因为这个词听起来一点也不对）"——但我得问问他们这个国家叫什么名字。请问，夫人，这里是新西兰还是澳大利亚？"（她说着试图行屈膝礼——想象一下在空中下落时行屈膝礼！你觉得你能做到吗？）</div>
      </div>
    `,
    demo2: `
      <div class="reading-block">
        <div class="reading-text-en">Once when I was six years old I saw a magnificent picture in a book, called True Stories from Nature, about the primeval forest. It was a picture of a boa constrictor in the act of swallowing an animal. Here is a copy of the drawing.</div>
        <div class="reading-text-zh">六岁那年，我在一本叫《真实的故事》的书里，看到了一幅描绘原始森林的壮观图画。画的是一条巨蟒正在吞食一只动物。这就是那幅画的摹本。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">In the book it said: "Boa constrictors swallow their prey whole, without chewing it. After that they are not able to move, and they sleep through the six months that they need for digestion."</div>
        <div class="reading-text-zh">书上写着："巨蟒把猎物囫囵吞下，不加咀嚼。这以后，它们就不能动弹了，它们就在长长的六个月的睡眠中消化这些食物。"</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">I pondered deeply, then, over the adventures of the jungle. And after some work with a colored pencil I succeeded in making my first drawing. My Drawing Number One. It looked like this: a boa constrictor swallowing an elephant.</div>
        <div class="reading-text-zh">当时，我对丛林中的奇遇想得很多，于是，我也用彩色铅笔画出了我的第一幅图画。我的第一号作品。它是这样的：一条巨蟒正在吞食一头大象。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">I showed my masterpiece to the grown-ups, and asked them whether the drawing frightened them. But they answered me: "Frighten? Why should any one be frightened by a hat?" My drawing was not a picture of a hat. It was a picture of a boa constrictor digesting an elephant. But since the grown-ups were not able to understand it, I made another drawing: I drew the inside of the boa constrictor, so that the grown-ups could see it clearly.</div>
        <div class="reading-text-zh">我把我的杰作拿给大人看，问他们这幅画是否吓到他们了。但他们回答说："害怕？为什么会有人被一顶帽子吓到？"我的画不是一顶帽子的画。它是一条巨蟒正在消化大象的画。但由于大人们无法理解，我又画了一幅：我画出了巨蟒的内部，这样大人们就能清楚地看到了。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">The grown-ups then advised me to lay aside my drawings of boa constrictors, whether from the inside or the outside, and devote myself instead to geography, history, arithmetic, and grammar. That is why, at the age of six, I gave up what might have been a magnificent career as a painter. I had been disheartened by the failure of my Drawing Number One and my Drawing Number Two.</div>
        <div class="reading-text-zh">于是大人们建议我放下画巨蟒的事情，无论是画内部还是外部，转而致力于地理、历史、算术和语法。这就是为什么在六岁时，我放弃了本可能成为伟大画家的职业。我的第一号和第二号画作的失败让我灰心丧气。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Grown-ups never understand anything by themselves, and it is tiresome for children to be always and forever explaining things to them. So then I chose another profession, and learned to pilot airplanes. I have flown a little over all parts of the world; and it is true that geography has been very useful to me. At a glance I can distinguish China from Arizona.</div>
        <div class="reading-text-zh">大人们自己永远什么都不懂，孩子们总是不得不一遍又一遍地向他们解释事情，真是烦人。于是我选择了另一个职业，学会了驾驶飞机。我飞过世界上的大部分地区；确实，地理学对我非常有用。我一眼就能分辨出中国和亚利桑那州。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">One evening, a little prince appeared out of nowhere. He asked me to draw him a sheep. I drew three sheep for him, but he was not satisfied. Finally, I drew a box and told him that the sheep was inside. He was very happy with that drawing. That is how I met the little prince.</div>
        <div class="reading-text-zh">一天晚上，一个小王子不知从哪里出现了。他让我给他画一只绵羊。我给他画了三只绵羊，但他都不满意。最后，我画了一个盒子，告诉他绵羊在里面。他对那幅画非常满意。我就是这样认识小王子的。</div>
      </div>
    `,
    demo3: `
      <div class="reading-block">
        <div class="reading-text-en">Dorothy lived in the midst of the great Kansas prairies, with Uncle Henry, who was a farmer, and Aunt Em, who was the farmer's wife. Their house was small, for the lumber to build it had to be carried by wagon many miles.</div>
        <div class="reading-text-zh">多萝西住在堪萨斯大草原的中部，和亨利叔叔、爱姆婶婶住在一起。亨利叔叔是个农夫，爱姆婶婶是农夫的妻子。他们的房子很小，因为建造房子的木材要用车从好几英里外运过来。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">There were four walls, a floor and a roof, which made one room; and this room contained a rusty looking cookstove, a cupboard for the dishes, a table, three or four chairs, and the beds. Uncle Henry and Aunt Em had a big bed in one corner, and Dorothy had a little bed in another corner.</div>
        <div class="reading-text-zh">房子只有一个房间，有四堵墙、一个地板和一个屋顶。房间里有一个看起来锈迹斑斑的炉灶、一个碗柜、一张桌子、三四把椅子和几张床。亨利叔叔和爱姆婶婶在一个角落里有一张大床，多萝西在另一个角落里有一张小床。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">There was no garret at all, and no cellar--except a small hole dug in the ground, called a cyclone cellar, where the family could go in case one of those great whirlwinds arose, mighty enough to crush any building in its path. It was reached by a trap door in the middle of the floor, from which a ladder led down into the small dark hole.</div>
        <div class="reading-text-zh">根本没有阁楼，也没有地窖——只有一个在地上挖的小洞，叫做旋风地窖，万一那些巨大的旋风刮起来，足以摧毁它路径上的任何建筑物时，全家人就可以躲进去。它通过地板中央的一个活板门进入，从那里有一个梯子通向那个小小的黑洞。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">When Dorothy stood in the doorway and looked around, she could see nothing but the great gray prairie on every side. Not a tree nor a house broke the broad sweep of flat country that reached to the edge of the sky in all directions. The sun had baked the plowed land into a gray mass, with little cracks running through it.</div>
        <div class="reading-text-zh">当多萝西站在门口环顾四周时，她看到的只有四周巨大的灰色草原。没有一棵树，也没有一栋房子打破这片广阔平坦的土地，它一直延伸到四面八方的天边。太阳把犁过的土地烤成了灰色的一团，上面布满了细小的裂缝。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">The grass was not green, for there had been no rain for many weeks. The sun had scorched the tops of the long grass until they were the same gray color to be seen everywhere. Once the house had been painted, but the sun blistered the paint and the rains washed it away, and now the house was as dull and gray as everything else.</div>
        <div class="reading-text-zh">草不是绿色的，因为已经好几个星期没下雨了。太阳把长草的顶部烤焦了，直到它们和到处看到的一样变成灰色。房子曾经刷过漆，但太阳把漆晒起泡了，雨水又把它冲掉了，现在房子和其他东西一样暗淡、灰色。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">When Aunt Em came there to live she was a young, pretty wife. The sun and wind had changed her, too. They had taken the sparkle from her eyes and left them a sober gray; they had taken the red from her cheeks and lips, and they were gray also. She was thin and gaunt, and never smiled now. When Dorothy, who was an orphan, first came to her, Aunt Em had been so startled by the child's laughter that she would scream and press her hand upon her heart whenever Dorothy's merry voice reached her ears.</div>
        <div class="reading-text-zh">爱姆婶婶刚到这里来住的时候，还是个年轻漂亮的妻子。太阳和风也改变了她。它们夺走了她眼睛里的光芒，留下了暗淡的灰色；它们夺走了她脸颊和嘴唇上的红色，它们也变成了灰色。她瘦骨嶙峋，现在从不微笑。当多萝西这个孤儿第一次来到她身边时，爱姆婶婶被孩子的笑声吓了一跳，每当多萝西欢快的声音传到她耳朵里，她就会尖叫着把手按在胸口上。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Uncle Henry never laughed. He worked hard from morning till night and did not know what joy was. He was gray also, from his long beard to his rough boots, and he looked stern and solemn, and rarely spoke. It was Toto that made Dorothy laugh, and saved her from growing as gray as her other surroundings.</div>
        <div class="reading-text-zh">亨利叔叔从不笑。他从早到晚辛勤工作，不知道什么是快乐。他也是灰色的，从他长长的胡子到粗糙的靴子，他看起来严肃庄重，很少说话。是托托让多萝西笑了，使她不至于像她周围的其他东西一样变得灰暗。</div>
      </div>
    `,
    demo4: `
      <div class="reading-block">
        <div class="reading-text-en">Squire Trelawney, Dr. Livesey, and the rest of these gentlemen having asked me to write down the whole particulars about Treasure Island, from the beginning to the end, keeping nothing back but the bearings of the island, and that only because there is still treasure not yet lifted, I take up my pen in the year of grace 17__ and go back to the time when my father kept the Admiral Benbow inn and the brown old seaman with the sabre cut first took up his lodging under our roof.</div>
        <div class="reading-text-zh">乡绅特里劳尼、利弗西医生以及其他几位先生要求我从头到尾写下宝岛的全部详情，除了岛上的方位之外什么都不要隐瞒，而不写方位只是因为那里还有未被取出的宝藏。我在公元17__年拿起笔，回忆起当年我父亲经营"本鲍上将"旅店，那个脸上有刀疤的棕色皮肤老水手第一次到我们家寄宿的情景。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">I remember him as if it were yesterday, as he came plodding to the inn door, his sea-chest following behind him in a hand-barrow--a tall, strong, heavy, nut-brown man, his tarry pigtail falling over the shoulders of his soiled blue coat, his hands ragged and scarred, with black, broken nails, and the sabre cut across one cheek, a dirty, livid white.</div>
        <div class="reading-text-zh">我记得他就像昨天一样，他拖着沉重的脚步来到旅店门口，他的航海箱放在手推车里跟在后面——一个高大、强壮、结实、皮肤呈坚果棕色的人，他涂着焦油的辫子垂在他肮脏的蓝色外套肩上，他的手粗糙且布满伤疤，指甲又黑又断，脸颊上有一道肮脏的、青白色的刀疤。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">I remember him looking round the cover, and whistling to himself as he did so, and then breaking out in that old sea-song that he sang so often afterwards: "Fifteen men on the dead man's chest--Yo-ho-ho, and a bottle of rum!" In the high, old tottering voice that seemed to have been tuned and broken at the capstan bars.</div>
        <div class="reading-text-zh">我记得他环顾了一下旅店的四周，一边吹着口哨，一边唱起了那首他后来经常唱的古老的海歌："十五个人站在死人胸膛上——哟嗬嗬，再来一瓶朗姆酒！"用那高亢、苍老、颤抖的声音，仿佛是在绞盘棒上被调过音又被弄断了一样。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Then he rapped on the door with a bit of stick like a handspike that he carried, and when my father appeared, called roughly for a glass of rum. This, when it was brought to him, he drank slowly, like a connoisseur, lingering on the taste and still looking about him at the cliffs and up at our signboard.</div>
        <div class="reading-text-zh">然后他用一根像他随身携带的手杆一样的棍子敲了敲门，当我父亲出现时，他粗鲁地要了一杯朗姆酒。这杯酒端来后，他慢慢地喝，像个鉴赏家一样，细细品味着味道，同时还在环顾四周的悬崖和我们的招牌。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">"This is a handy cove," says he, at length; "and a pleasant sittyated grog-shop. Much company, mate?" My father told him no, very little company, the more was the pity.</div>
        <div class="reading-text-zh">"这是个方便的小海湾，"他终于说道，"也是个位置不错的酒馆。客人多吗，伙计？"我父亲告诉他不多，客人很少，真可惜。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">"Well, then," said he, "this is the berth for me. Here you, matey," he cried to the man who trundled the barrow; "bring up alongside and help me ashore." He gave his hand and hoisted himself up with a strength that seemed incredible in so old a man. He took up his quarters in the inn, and from that day forth, a day seldom passed that he did not come down and ask for a glass of rum.</div>
        <div class="reading-text-zh">"那么，"他说，"这就是我的住处了。喂，你，伙计，"他对推手推车的人喊道，"靠过来帮我上岸。"他伸出手，用一种在这么老的人身上似乎不可思议的力量把自己拉了上来。他在旅店里住了下来，从那天起，几乎每天他都会下来要一杯朗姆酒。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">He was a very silent man by custom. All day he hung round the cove or upon the cliffs with a brass telescope; all evening he sat in a corner of the parlor next the fire and drank rum and water very strong. Mostly he would not speak when spoken to; only look up sudden and fierce and blow through his nose like a fog-horn; and we and the people who came about our house soon learned to let him be.</div>
        <div class="reading-text-zh">他习惯上是个非常沉默寡言的人。整天他拿着一个黄铜望远镜在海湾周围或悬崖上闲逛；整个晚上他坐在客厅靠近壁炉的角落里，喝着非常浓烈的朗姆酒和水。大多数时候，别人跟他说话他都不回答；只是突然猛地抬起头，凶狠地看着对方，像雾号一样从鼻子里呼出一口气；我们和来我们家的人很快就学会了不去打扰他。</div>
      </div>
    `,
    demo5: `
      <div class="reading-block">
        <div class="reading-text-en">Tom Sawyer lives with his Aunt Polly and his half-brother Sid. He skips school to swim and is made to whitewash the fence the next day as punishment. He cleverly persuades his friends to trade him small treasures for the privilege of doing his work.</div>
        <div class="reading-text-zh">汤姆·索亚和波莉姨妈以及同父异母弟弟希德住在一起。他逃学去游泳，第二天被罚粉刷篱笆墙。他聪明地说服朋友们用小玩意儿来换取替他干活的特权。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Tom's trick works so well that he acquires a whole set of toys, including a kite, a brass doorknob, and a dead rat on a string. He then trades these treasures to other boys for tickets that Sunday school awards for memorizing Bible verses. With enough tickets, he wins a prize: a Bible, even though he has not memorized a single verse.</div>
        <div class="reading-text-zh">汤姆的诡计非常奏效，他获得了一整套玩具，包括一只风筝、一个黄铜门把手和一根绳子上挂着的死老鼠。然后他把这些宝贝卖给其他男孩，换取主日学校为背诵圣经经文颁发的票券。凭借足够的票券，他赢得了一份奖品：一本圣经，尽管他一句经文也没有背诵。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">At school, Tom falls in love with a new girl, Becky Thatcher, and tries to impress her. He pretends to be brave and shows off by sitting with her. They become "engaged," but their engagement falls apart when Tom mentions that he was previously engaged to Amy Lawrence.</div>
        <div class="reading-text-zh">在学校里，汤姆爱上了一个新来的女孩贝基·撒切尔，并试图给她留下深刻印象。他假装勇敢，坐在她身边炫耀。他们"订婚"了，但当汤姆提到他之前曾与艾米·劳伦斯订过婚时，他们的订婚破裂了。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Later, Tom runs away with his friend Huckleberry Finn to Jackson's Island, where they play at being pirates. The town thinks they have drowned, and holds a funeral for them. But Tom and Huck attend their own funeral, surprising everyone.</div>
        <div class="reading-text-zh">后来，汤姆和他的朋友哈克贝利·费恩跑到杰克逊岛，在那里玩海盗游戏。镇上的人以为他们淹死了，为他们举行了葬礼。但汤姆和哈克参加了自己的葬礼，让所有人都大吃一惊。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Tom and Huck also witness a murder committed by Injun Joe. They run away in fear, but later Tom testifies against Joe in court, putting him in jail. When Joe escapes, Tom and Huck go searching for treasure in a haunted house, where they find Injun Joe and his accomplice hiding out.</div>
        <div class="reading-text-zh">汤姆和哈克还目睹了印第安·乔犯下的一起谋杀案。他们吓得逃跑了，但后来汤姆在法庭上指证乔，把他送进了监狱。当乔逃跑后，汤姆和哈克去鬼屋寻宝，在那里他们发现印第安·乔和他的同伙躲藏在那里。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Eventually, Tom and Huck find the treasure in a cave, where Injun Joe is trapped and dies. They become rich, and the town celebrates their success. Tom Sawyer grows up a bit during these adventures, learning valuable lessons about courage, friendship, and honesty.</div>
        <div class="reading-text-zh">最终，汤姆和哈克在一个山洞里找到了宝藏，印第安·乔被困在那里并死去。他们变得富有，镇上的人庆祝他们的成功。汤姆·索亚在这些冒险中长大了一些，学到了关于勇气、友谊和诚实的宝贵教训。</div>
      </div>
    `,
    demo6: `
      <div class="reading-block">
        <div class="reading-text-en">Buck did not read the newspapers, or he would have known that trouble was brewing, not alone for himself, but for every tide-water dog, strong of muscle and with warm, long hair, from Puget Sound to San Diego. Because men, groping in the Arctic darkness, had found a yellow metal, and because steamship and transportation companies were booming the find, thousands of men were rushing into the Northland.</div>
        <div class="reading-text-zh">巴克没有看报纸，否则他就会知道麻烦正在酝酿之中，不仅是对他自己，而是对从普吉特海湾到圣迭戈的每一只强壮有力、长毛披身的水狗。因为人们在北极的黑暗中找到了一种黄色的金属，又因为轮船和运输公司在大肆宣扬这一发现，成千上万的人正涌向北方。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">These men wanted dogs, and the dogs they wanted were heavy dogs, with strong muscles by which to toil, and furry coats to protect them from the frost. Buck lived at a big house in the sun-kissed Santa Clara Valley. Judge Miller's place, it was called. It stood back from the road, half hidden among the trees, through which glimpses could be caught of the wide cool veranda that ran around its four sides.</div>
        <div class="reading-text-zh">这些人需要狗，他们需要的是强壮的狗，有着可以劳作的强壮肌肉，和可以保护它们免受严寒的毛茸茸的皮毛。巴克住在阳光明媚的圣克拉拉山谷里的一座大房子里。那地方叫米勒法官的庄园。它远离大路，半隐半现地坐落在树林中，透过树林可以瞥见环绕四周的宽阔凉爽的走廊。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">The house was approached by graveled driveways which wound about through wide-spreading lawns and under the interlacing boughs of tall poplars. At the rear things were on even a more spacious scale than at the front. There were great stables, where a dozen grooms and boys held forth, rows of vine-clad servants' cottages, an endless and orderly array of outhouses, long grape arbors, green pastures, orchards, and berry patches.</div>
        <div class="reading-text-zh">通往房子的是碎石车道，车道蜿蜒穿过宽阔的草坪，穿过高大杨树交错的树枝。房子后面的规模甚至比前面更宽敞。有巨大的马厩，里面住着十几名马夫和男孩，一排排爬满藤蔓的仆人小屋，数不清的整齐排列的外屋，长长的葡萄架，绿色的牧场，果园和浆果地。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Here Buck ruled over the whole realm. Here he was born, and here he had lived the four years of his life. It was true, there were other dogs, There could not but be other dogs on so vast a place, but they did not count. They came and went, resided in the populous kennels, or lived obscurely in the recesses of the house after the fashion of Toots, the Japanese pug, or Ysabel, the Mexican hairless,—strange creatures that rarely put nose out of doors or set foot to ground.</div>
        <div class="reading-text-zh">在这里，巴克统治着整个王国。他在这里出生，在这里度过了他生命中的四年。确实，还有其他的狗。在这么大的地方不可能没有其他狗，但它们不算数。它们来来去去，住在拥挤的狗窝里，或者像日本哈巴狗图茨或墨西哥无毛狗伊莎贝尔那样，默默无闻地住在房子的深处——这些奇怪的生物很少把鼻子伸出门外或把脚踩在地上。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">But Buck was neither house-dog nor kennel-dog. The whole realm was his. He plunged into the swimming tank or went hunting with the Judge's sons; he escorted Mollie and Alice, the Judge's daughters, on long twilight or early morning rambles; on wintry nights he lay at the Judge's feet before the roaring library fire; he carried the Judge's grandsons on his back, or rolled them in the grass, and guarded their footsteps through wild adventures down to the fountain in the stable yard, and even beyond, where the paddocks were, and the berry patches.</div>
        <div class="reading-text-zh">但巴克既不是家犬，也不是窝犬。整个王国都是他的。他跳进游泳池，或者和法官的儿子们一起去打猎；他陪伴法官的女儿莫莉和爱丽丝在漫长的黄昏或清晨漫步；在寒冷的夜晚，他躺在法官的脚边，在图书馆熊熊燃烧的炉火前；他把法官的孙子们背在背上，或者在草地上和他们打滚，并在他们疯狂的冒险中守护着他们的脚步，一直到马厩院子里的喷泉，甚至更远的牧场和浆果地。</div>
      </div>
      <div class="reading-block">
        <div class="reading-text-en">Among the terriers he stalked imperiously, and Toots and Ysabel he utterly ignored, for he was king—king over all creeping, crawling, flying things of Judge Miller's place, humans included. His father, Elmo, a huge St. Bernard, had been the Judge's inseparable companion, and Buck bid fair to follow in the way of his father. He was not so large—he weighed only one hundred and forty pounds—for his mother, Shep, had been a Scotch shepherd dog. Nevertheless, one hundred and forty pounds, to which was added the dignity that comes of good living and universal respect, enabled him to carry himself in right royal fashion.</div>
        <div class="reading-text-zh">在梗犬中，他傲慢地昂首阔步，对图茨和伊莎贝尔完全不理不睬，因为他是国王——统治着米勒法官庄园里所有爬行、蠕动、飞行的东西，包括人类。他的父亲埃尔莫，一只巨大的圣伯纳犬，曾是法官形影不离的伙伴，巴克有望追随他父亲的脚步。他没有那么大——他只有一百四十磅重——因为他的母亲谢普是一只苏格兰牧羊犬。尽管如此，一百四十磅的体重，再加上良好的生活和普遍的尊重带来的尊严，使他能够以真正的皇家气派行事。</div>
      </div>
    `,
  };
  
  paper.innerHTML = contents[bookId] || contents.demo1;
  setupWordClick();
}

function loadDocumentContent(doc) {
  const paper = document.getElementById('readerPaper');
  if (!paper || !doc) return;
  
  if (doc.blocks && doc.blocks.length > 0) {
    paper.innerHTML = doc.blocks.map((block, index) => `
      <div class="reading-block" data-block-index="${index}">
        <div class="reading-text-en">${escapeHtml(block.text_en)}</div>
        <div class="reading-text-zh">${escapeHtml(block.text_zh || '翻译中...')}</div>
      </div>
    `).join('');
  } else {
    const blocks = (doc.content || '').split(/\n\n+/).filter(b => b.trim());
    paper.innerHTML = blocks.map((block, index) => `
      <div class="reading-block" data-block-index="${index}">
        <div class="reading-text-en">${escapeHtml(block.trim())}</div>
        <div class="reading-text-zh"></div>
      </div>
    `).join('');
  }
  
  setupWordClick();
}

function speakPage() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  const text = paper.innerText;
  if (!text) {
    showToast('没有可朗读的内容', 'error');
    return;
  }

  if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
    try {
      window.AndroidDictionary.speak(text);
      showToast('开始朗读', 'info');
      return;
    } catch (e) {
      console.log('Android TTS failed, falling back to Web Speech API');
    }
  }
  
  if (!('speechSynthesis' in window)) {
    showToast('设备不支持语音合成', 'error');
    return;
  }
  
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-US';
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
  showToast('开始朗读', 'info');
}

function setupWordClick() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  paper.addEventListener('click', handleWordLookup);
}

async function handleWordLookup(e) {
  const wordEl = e.target.closest('.clickable-word');
  const selection = window.getSelection();
  const selectionText = selection ? selection.toString().trim() : '';
  
  if (selectionText && selectionText.split(/\s+/).length > 1) {
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    showWordPopover({ 
      word: '句子翻译', 
      pronunciation: '', 
      translation: '查询中...', 
      example: selectionText 
    }, rect.left, rect.top - 10);
    
    try {
      const translation = await translateText(selectionText);
      renderWordPopover({
        word: selectionText,
        pronunciation: '',
        translation: translation,
        example: ''
      });
    } catch (err) {
      renderWordPopover({
        word: selectionText,
        pronunciation: '',
        translation: '暂无释义',
        example: ''
      });
    }
    return;
  }
  
  if (wordEl) {
    const word = wordEl.textContent.trim();
    if (!word || !/^[a-zA-Z'-]+$/.test(word)) return;
    
    const rect = wordEl.getBoundingClientRect();
    
    const cachedData = typeof getWordDataFromCache === 'function' ? getWordDataFromCache(word) : null;
    if (cachedData) {
      showWordPopover(cachedData, rect.left, rect.top - 10);
      return;
    }
    
    showWordPopover({ word, pronunciation: '', translation: '查询中...', example: '' }, rect.left, rect.top - 10);
    
    try {
      const data = await getWordData(word);
      renderWordPopover(data);
    } catch (err) {
      console.error('Word lookup error:', err);
    }
  }
}

function setupSentenceSelection() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  paper.addEventListener('mouseup', handleSentenceSelection);
  paper.addEventListener('touchend', handleSentenceSelection);
}

function handleSentenceSelection(e) {
  const selection = window.getSelection();
  if (!selection) return;
  
  const selectionText = selection.toString().trim();
  if (!selectionText) return;
  
  const wordCount = selectionText.split(/\s+/).length;
  if (wordCount <= 1) return;
  
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  showWordPopover({ 
    word: '句子翻译', 
    pronunciation: '', 
    translation: '查询中...', 
    example: selectionText 
  }, rect.left, rect.top - 10);
  
  translateText(selectionText).then(translation => {
    renderWordPopover({
      word: selectionText,
      pronunciation: '',
      translation: translation,
      example: ''
    });
  }).catch(() => {
    renderWordPopover({
      word: selectionText,
      pronunciation: '',
      translation: '暂无释义',
      example: ''
    });
  });
}

function lazyTranslateVisibleSentences() {
  if (typeof lazyTranslateVisibleParagraphs !== 'undefined') {
    lazyTranslateVisibleParagraphs();
  }
}

function handleScrollForLazyTranslate() {
  if (typeof lazyTranslateVisibleParagraphs !== 'undefined') {
    requestAnimationFrame(lazyTranslateVisibleParagraphs);
  }
}

function renderPracticePage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="practice-page">
      <div class="card">
        <h2>✏️ 练习模式</h2>
        <p class="text-muted">练习功能开发中...</p>
        <button class="btn-secondary" onclick="navigateTo('')">← 返回首页</button>
      </div>
    </div>
  `;
}

function renderVocabPage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="vocab-page">
      <div class="card">
        <h2>📝 生词本</h2>
        <div id="vocabStats" class="vocab-stats">
          <span>加载中...</span>
        </div>
      </div>
      
      <div id="vocabGrid" class="vocab-grid"></div>
      
      <div class="card">
        <h3>📚 复习推荐</h3>
        <div id="reviewArea" class="review-area"></div>
      </div>
    </div>
  `;
  loadVocab();
}

function sourceIcon(platform) {
  if (platform === 'wordbook') return '📚';
  if (platform === 'reading') return '📖';
  if (platform === 'web') return '🌐';
  if (platform === 'bilibili') return '📺';
  if (platform === 'youtube') return '▶';
  return '📚';
}

function dueStatus(card) {
  const due = new Date(card.due).getTime();
  const now = Date.now();
  if (due <= now) return { text: '需复习', cls: 'now' };
  const diff = due - now;
  if (diff < 86400000) return { text: '即将到期', cls: 'soon' };
  return { text: `${Math.ceil(diff / 86400000)} 天后`, cls: 'later' };
}

async function loadVocab() {
  const grid = document.getElementById('vocabGrid');
  const stats = document.getElementById('vocabStats');
  if (!grid || !stats) return;
  
  try {
    const items = await getVocab();
    renderVocabList(items);
    renderVocabStats(items);
    renderReview(items);
  } catch (e) {
    grid.innerHTML = `<div class="empty-state"><h3>加载失败</h3><p>${escapeHtml(e.message)}</p></div>`;
  }
}

function renderVocabStats(items) {
  const stats = document.getElementById('vocabStats');
  if (!stats) return;
  
  const dueCount = items.filter(i => new Date(i.due).getTime() <= Date.now()).length;
  stats.innerHTML = `
    <span>总计: ${items.length}</span>
    <span>需复习: ${dueCount}</span>
    <span>已掌握: ${items.filter(i => i.reps >= 3).length}</span>
  `;
}

function renderVocabList(items) {
  const grid = document.getElementById('vocabGrid');
  if (!grid) return;
  
  if (items.length === 0) {
    grid.innerHTML = `<div class="empty-state"><h3>还没有生词</h3><p>在视频学习、英文阅读或词书页面把单词加入学习吧！</p></div>`;
    return;
  }
  
  grid.innerHTML = items.map(card => {
    const ds = dueStatus(card);
    return `
      <div class="vocab-card">
        <div class="word-header">
          <span class="word-title">${escapeHtml(card.word)}</span>
          <button class="btn-danger" onclick="deleteVocabItem(${card.id})">删除</button>
        </div>
        <div class="word-phonetic">${escapeHtml(card.pronunciation || '')}</div>
        <div class="word-def">${escapeHtml(card.translation || card.definition || '')}</div>
        ${card.sentence ? `<div class="word-context">"${escapeHtml(card.sentence)}"</div>` : ''}
        ${card.source_title ? `<div class="word-source">${sourceIcon(card.source_platform)} ${escapeHtml(card.source_title)}</div>` : ''}
        <div class="word-meta">
          <span>复习 ${card.reps} 次</span>
          <span class="due-badge ${ds.cls}">${ds.text}</span>
        </div>
      </div>
    `;
  }).join('');
}

async function deleteVocabItem(id) {
  if (!confirm('确定删除这个生词吗？')) return;
  try {
    await deleteVocab(id);
    await loadVocab();
    showToast('已删除', 'success');
  } catch (e) {
    showToast('删除失败', 'error');
  }
}

let reviewQueue = [];
let reviewIdx = 0;
let showAnswer = false;

function renderReview(items) {
  reviewQueue = items.filter(i => new Date(i.due).getTime() <= Date.now()).slice(0, 10);
  reviewIdx = 0;
  showAnswer = false;
  renderReviewCard();
}

function renderReviewCard() {
  const area = document.getElementById('reviewArea');
  if (!area) return;
  
  if (reviewIdx >= reviewQueue.length) {
    area.innerHTML = `
      <div class="empty-state">
        <h3>🎉 全部复习完成！</h3>
        <p>暂时没有需要复习的单词了。去看新视频收藏更多生词吧。</p>
      </div>
    `;
    return;
  }
  
  const card = reviewQueue[reviewIdx];
  const progress = `${reviewIdx + 1} / ${reviewQueue.length}`;
  
  if (!showAnswer) {
    area.innerHTML = `
      <div class="review-card">
        <div class="review-progress">${progress}</div>
        ${card.sentence ? `<div class="review-context">"${escapeHtml(card.sentence)}"</div>` : ''}
        ${card.sentence_translation ? `<div class="review-context-zh">${escapeHtml(card.sentence_translation)}</div>` : ''}
        <p class="review-hint">看句子猜词义，想好了再显示答案</p>
        <button id="showAnswerBtn" class="btn-primary">显示答案</button>
      </div>
    `;
    document.getElementById('showAnswerBtn').addEventListener('click', () => {
      showAnswer = true;
      renderReviewCard();
      speakWord(card.word);
    });
    return;
  }
  
  area.innerHTML = `
    <div class="review-card">
      <div class="review-progress">${progress}</div>
      <div class="word-big">${escapeHtml(card.word)}</div>
      <div class="word-phonetic-big">${escapeHtml(card.pronunciation || '')}</div>
      <div class="word-def-big">${escapeHtml(card.translation || card.definition || '')}</div>
      <div class="review-buttons">
        <button class="review-btn again" onclick="handleReview(${card.id}, 1)">忘记</button>
        <button class="review-btn hard" onclick="handleReview(${card.id}, 2)">困难</button>
        <button class="review-btn good" onclick="handleReview(${card.id}, 3)">良好</button>
        <button class="review-btn easy" onclick="handleReview(${card.id}, 4)">简单</button>
      </div>
    </div>
  `;
}

async function handleReview(vocabId, rating) {
  try {
    const vocab = await getVocabById(vocabId);
    if (vocab) {
      const now = new Date();
      let days = 1;
      if (rating === 1) days = 1;
      else if (rating === 2) days = 3;
      else if (rating === 3) days = 7;
      else if (rating === 4) days = 14;
      
      const newDue = new Date(now.getTime() + days * 24 * 60 * 60 * 1000);
      await updateVocab(vocabId, {
        reps: vocab.reps + 1,
        due: newDue.toISOString()
      });
    }
    
    reviewIdx++;
    showAnswer = false;
    renderReviewCard();
    await loadVocab();
  } catch (e) {
    console.error('Failed to update review:', e);
  }
}

function renderPracticePage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="practice-page">
      <div class="card">
        <h2>✏️ 练习模式</h2>
        <div class="practice-tabs">
          <button class="tab-btn active" onclick="startPractice('spelling')">📝 拼写</button>
          <button class="tab-btn" onclick="startPractice('listening')">🎧 听力</button>
          <button class="tab-btn" onclick="startPractice('reading')">📖 阅读</button>
        </div>
        <div id="practiceArea" class="practice-area">
          <p style="color:var(--muted);text-align:center;padding:40px;">选择一种练习类型开始</p>
        </div>
      </div>
    </div>
  `;
}

let practiceType = 'spelling';
let practiceQuestions = [];
let practiceIdx = 0;

async function startPractice(type) {
  practiceType = type;
  const tabs = document.querySelectorAll('.practice-tabs .tab-btn');
  tabs.forEach(t => t.classList.remove('active'));
  tabs.forEach(t => {
    if (t.textContent.includes(type === 'spelling' ? '拼写' : type === 'listening' ? '听力' : '阅读')) {
      t.classList.add('active');
    }
  });
  
  const area = document.getElementById('practiceArea');
  if (!area) return;
  
  area.innerHTML = `<p style="color:var(--muted);text-align:center;padding:40px;">加载中...</p>`;
  
  try {
    const vocab = await getVocab();
    if (vocab.length < 5) {
      area.innerHTML = `
        <div class="empty-state">
          <h3>暂无练习数据</h3>
          <p>请先在视频、阅读或词书中收藏一些单词。</p>
        </div>
      `;
      return;
    }
    
    practiceQuestions = generatePracticeQuestions(vocab, type, 10);
    practiceIdx = 0;
    renderPracticeQuestion();
  } catch (e) {
    area.innerHTML = `<p style="color:var(--danger)">加载失败: ${escapeHtml(e.message)}</p>`;
  }
}

function generatePracticeQuestions(vocab, type, count) {
  const questions = [];
  const shuffled = [...vocab].sort(() => Math.random() - 0.5);
  
  for (let i = 0; i < Math.min(count, shuffled.length); i++) {
    const item = shuffled[i];
    if (type === 'spelling') {
      questions.push({
        question: item.translation || item.definition || '请拼写这个单词',
        answer: item.word,
        pronunciation: item.pronunciation
      });
    } else if (type === 'listening') {
      questions.push({
        question: '听录音并拼写单词',
        answer: item.word,
        pronunciation: item.pronunciation
      });
    } else if (type === 'reading') {
      const choices = [item.word];
      while (choices.length < 4) {
        const randomItem = shuffled[Math.floor(Math.random() * shuffled.length)];
        if (!choices.includes(randomItem.word)) {
          choices.push(randomItem.word);
        }
      }
      questions.push({
        question: item.translation || item.definition || '请选择正确的单词',
        answer: item.word,
        choices: choices.sort(() => Math.random() - 0.5)
      });
    }
  }
  
  return questions;
}

function renderPracticeQuestion() {
  const area = document.getElementById('practiceArea');
  if (!area) return;
  
  if (practiceIdx >= practiceQuestions.length) {
    area.innerHTML = `
      <div class="empty-state">
        <h3>🎉 练习完成！</h3>
        <p>共完成 ${practiceQuestions.length} 道题。</p>
        <button class="btn-primary" onclick="startPractice('${practiceType}')">再来一轮</button>
      </div>
    `;
    return;
  }
  
  const q = practiceQuestions[practiceIdx];
  
  if (practiceType === 'spelling') {
    area.innerHTML = `
      <div class="practice-question">
        <div class="pq-text">${escapeHtml(q.question)}</div>
        ${q.pronunciation ? `<div style="color:var(--accent);margin-bottom:16px;">${escapeHtml(q.pronunciation)}</div>` : ''}
        <input type="text" id="answerInput" class="practice-input" placeholder="输入英文单词..." autocomplete="off" />
        <div><button class="btn-primary" onclick="checkSpellingAnswer('${q.answer}')">提交</button></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const input = document.getElementById('answerInput');
    input.focus();
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') checkSpellingAnswer(q.answer);
    });
  } else if (practiceType === 'listening') {
    area.innerHTML = `
      <div class="practice-question">
        <button class="tts-btn" onclick="speakWord('${q.answer}')">🔊 点击播放</button>
        <div class="pq-text">听录音并拼写单词</div>
        <input type="text" id="answerInput" class="practice-input" placeholder="输入听到的单词..." autocomplete="off" />
        <div><button class="btn-primary" onclick="checkSpellingAnswer('${q.answer}')">提交</button></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    setTimeout(() => speakWord(q.answer), 500);
    const input = document.getElementById('answerInput');
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') checkSpellingAnswer(q.answer);
    });
  } else if (practiceType === 'reading') {
    area.innerHTML = `
      <div class="practice-question">
        <div class="pq-text">${escapeHtml(q.question)}</div>
        <div class="choice-list" id="choiceList"></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const list = document.getElementById('choiceList');
    q.choices.forEach((choice) => {
      const btn = document.createElement('button');
      btn.className = 'choice-item';
      btn.textContent = choice;
      btn.addEventListener('click', () => {
        const msg = document.getElementById('resultMsg');
        const buttons = list.querySelectorAll('.choice-item');
        buttons.forEach((b) => { b.disabled = true; });
        if (choice === q.answer) {
          btn.classList.add('correct');
          msg.textContent = '✅ 正确！';
          msg.className = 'result-msg correct';
        } else {
          btn.classList.add('wrong');
          buttons.forEach((b) => {
            if (b.textContent === q.answer) b.classList.add('correct');
          });
          msg.textContent = `❌ 错误！正确答案: ${q.answer}`;
          msg.className = 'result-msg wrong';
        }
        speakWord(q.answer);
        setTimeout(() => { practiceIdx += 1; renderPracticeQuestion(); }, 2000);
      });
      list.appendChild(btn);
    });
  }
}

function checkSpellingAnswer(correctAnswer) {
  const input = document.getElementById('answerInput');
  const msg = document.getElementById('resultMsg');
  const answer = input.value.trim();
  
  if (answer.toLowerCase() === correctAnswer.toLowerCase()) {
    msg.textContent = '✅ 正确！';
    msg.className = 'result-msg correct';
    speakWord(correctAnswer);
  } else {
    msg.textContent = `❌ 错误！正确答案: ${correctAnswer}`;
    msg.className = 'result-msg wrong';
  }
  
  setTimeout(() => { practiceIdx += 1; renderPracticeQuestion(); }, 2000);
}