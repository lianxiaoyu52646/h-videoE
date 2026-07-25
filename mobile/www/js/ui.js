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
    await saveWord(word, {});
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

function renderWordbooksPage() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="wordbooks-page">
      <div class="card">
        <h2>我的单词本</h2>
        <div id="wordbooksList"></div>
        <button class="btn-secondary" onclick="createWordbook()">+ 创建单词本</button>
      </div>
    </div>
  `;
  loadWordbooks();
}

async function loadWordbooks() {
  const list = document.getElementById('wordbooksList');
  if (!list) return;
  
  const wordbooks = await getWordbooks();
  
  if (wordbooks.length === 0) {
    list.innerHTML = '<p class="text-muted">暂无单词本，点击下方按钮创建</p>';
    return;
  }
  
  list.innerHTML = wordbooks.map(wb => `
    <div class="wordbook-item" onclick="openWordbook(${wb.id})">
      <div class="wordbook-item-name">${escapeHtml(wb.name)}</div>
      <div class="wordbook-item-count">加载中...</div>
    </div>
  `).join('');
  
  for (const wb of wordbooks) {
    const entries = await getWordbookEntries(wb.id);
    const el = list.querySelector(`[onclick="openWordbook(${wb.id})"] .wordbook-item-count`);
    if (el) el.textContent = `${entries.length} 个单词`;
  }
}

async function createWordbook() {
  const name = prompt('请输入单词本名称：');
  if (!name) return;
  
  await addWordbook(name);
  showToast('创建成功', 'success');
  loadWordbooks();
}

async function openWordbook(id) {
  const wordbook = await getWordbook(id);
  const entries = await getWordbookEntries(id);
  
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="wordbook-detail-page">
      <div class="card">
        <div class="flex justify-between items-center mb-4">
          <button class="btn-secondary" onclick="renderWordbooksPage()">← 返回</button>
          <h2>${escapeHtml(wordbook?.name || '单词本')}</h2>
          <span></span>
        </div>
        <div id="wordbookEntries"></div>
      </div>
    </div>
  `;
  
  renderWordbookEntries(entries);
}

function renderWordbookEntries(entries) {
  const container = document.getElementById('wordbookEntries');
  if (!container) return;
  
  if (entries.length === 0) {
    container.innerHTML = '<p class="text-muted">暂无单词</p>';
    return;
  }
  
  container.innerHTML = entries.map((entry, index) => `
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
            <button class="wordbook-speak-btn" onclick="speakWord('${escapeHtml(entry.word)}')">🔊</button>
          </div>
        </div>
        <div class="wordbook-entry-translation">${escapeHtml(entry.translation || '暂无释义')}</div>
        ${entry.example ? `<div class="wordbook-entry-example">${escapeHtml(entry.example)}</div>` : ''}
      </div>
    </article>
  `).join('');
}

function renderReaderPage() {
  console.log('=== renderReaderPage called ===');
  const content = document.getElementById('pageContent');
  console.log('pageContent:', !!content);
  
  content.innerHTML = `
    <div class="reader-page">
      <div class="card">
        <h2>📖 阅读器</h2>
        <p class="text-muted">请选择一本书籍开始阅读</p>
        <div id="bookList"></div>
      </div>
    </div>
  `;
  
  setTimeout(loadBookList, 100);
}

function loadBookList() {
  const list = document.getElementById('bookList');
  console.log('loadBookList: bookList element:', !!list);
  
  if (!list) {
    console.error('loadBookList: bookList NOT FOUND');
    return;
  }
  
  const books = [
    { id: 'demo1', title: 'Alice in Wonderland', author: 'Lewis Carroll', words: '15,000' },
    { id: 'demo2', title: 'The Little Prince', author: 'Antoine de Saint-Exupéry', words: '8,000' },
    { id: 'demo3', title: 'The Wizard of Oz', author: 'L. Frank Baum', words: '20,000' }
  ];
  
  list.innerHTML = books.map(book => `
    <div class="book-item" data-book-id="${book.id}">
      <div class="book-item-title">${escapeHtml(book.title)}</div>
      <div class="book-item-meta">${escapeHtml(book.author)} · ${book.words} 词</div>
    </div>
  `).join('');
  
  list.addEventListener('click', (e) => {
    const bookItem = e.target.closest('.book-item');
    if (bookItem) {
      const bookId = bookItem.dataset.bookId;
      openBook(bookId);
    }
  });
}

function openBook(bookId) {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="reading-view">
      <div class="reader-topbar">
        <div class="reader-topbar-inner">
          <button class="btn-secondary" onclick="renderReaderPage()">← 返回</button>
          <div class="reader-topbar-title">Alice in Wonderland</div>
          <div class="reader-topbar-actions">
            <button class="btn-secondary btn-sm">🔊</button>
            <button class="btn-secondary btn-sm">📝</button>
          </div>
        </div>
      </div>
      <div class="reader-paper" id="readerPaper"></div>
    </div>
  `;
  loadReadingContent();
}

function loadReadingContent() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  const sampleText = `
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
  `;
  
  paper.innerHTML = sampleText;
  setupWordClick();
}

function setupWordClick() {
  const paper = document.getElementById('readerPaper');
  if (!paper) return;
  
  paper.addEventListener('mouseup', handleWordLookup);
  paper.addEventListener('touchend', handleWordLookup);
  paper.addEventListener('click', handleWordLookup);
  
  document.addEventListener('mouseup', (e) => {
    if (paper.contains(e.target)) {
      handleWordLookup(e);
    }
  }, { capture: true });
}

async function handleWordLookup(e) {
  const paper = document.getElementById('readerPaper');
  const textEn = e.target.closest('.reading-text-en') || paper.querySelector('.reading-text-en');
  
  if (!textEn) return;
  
  const selection = window.getSelection();
  const selectionText = selection ? selection.toString().trim() : '';
  
  if (!selectionText) {
    const range = document.caretRangeFromPoint(e.clientX, e.clientY);
    if (range) {
      const text = textEn.textContent;
      const offset = range.startOffset;
      let start = offset;
      let end = offset;
      
      while (start > 0 && /[a-zA-Z'-]/.test(text[start - 1])) start--;
      while (end < text.length && /[a-zA-Z'-]/.test(text[end])) end++;
      
      const word = text.substring(start, end);
      if (word && /^[a-zA-Z'-]+$/.test(word)) {
        const rect = e.target.getBoundingClientRect();
        showWordPopover({ word, pronunciation: '', translation: '查询中...', example: '' }, rect.left, rect.top - 10);
        const data = await getWordData(word);
        renderWordPopover(data);
      }
    }
    return;
  }
  
  const word = selectionText.split(/\s+/)[0];
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  
  showWordPopover({ word, pronunciation: '', translation: '查询中...', example: '' }, rect.left, rect.top - 10);
  
  const data = await getWordData(word);
  renderWordPopover(data);
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