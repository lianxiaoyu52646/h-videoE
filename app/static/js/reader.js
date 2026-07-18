// ── 阅读器 /reader?id= — 书页流式 + Popover 查词 ──
const params = new URLSearchParams(location.search);
const docId = parseInt(params.get('id') || '0', 10);

const readerTitle = document.getElementById('readerTitle');
const statusMsg = document.getElementById('statusMsg');
const blockList = document.getElementById('blockList');
const wordPopover = document.getElementById('wordPopover');
const wordPopoverBody = document.getElementById('wordPopoverBody');
const saveWordBtn = document.getElementById('saveWordBtn');
const speakWordBtn = document.getElementById('speakWordBtn');
const expandWordBtn = document.getElementById('expandWordBtn');
const closePopover = document.getElementById('closePopover');
const displayMode = document.getElementById('displayMode');
const fontSmaller = document.getElementById('fontSmaller');
const fontBigger = document.getElementById('fontBigger');
const fontSizeLabel = document.getElementById('fontSizeLabel');
const ttsToggle = document.getElementById('ttsToggle');
const stopTts = document.getElementById('stopTts');
const readProgressFill = document.getElementById('readProgressFill');
const readProgressText = document.getElementById('readProgressText');
const notesPanel = document.getElementById('notesPanel');
const notesList = document.getElementById('notesList');
const newNoteText = document.getElementById('newNoteText');
const addNoteBtn = document.getElementById('addNoteBtn');
const toggleNotes = document.getElementById('toggleNotes');
const closeNotes = document.getElementById('closeNotes');
const toggleSettings = document.getElementById('toggleSettings');
const settingsPanel = document.getElementById('settingsPanel');
const selectionToolbar = document.getElementById('selectionToolbar');
const highlightBtn = document.getElementById('highlightBtn');
const noteSelectionBtn = document.getElementById('noteSelectionBtn');
const lookupSelectionBtn = document.getElementById('lookupSelectionBtn');
const toggleToc = document.getElementById('toggleToc');
const closeToc = document.getElementById('closeToc');
const tocPanel = document.getElementById('tocPanel');
const tocList = document.getElementById('tocList');
const vocabStatsBar = document.getElementById('vocabStatsBar');
const vocabStatsText = document.getElementById('vocabStatsText');
const vocabReviewLink = document.getElementById('vocabReviewLink');
const readerTheme = document.getElementById('readerTheme');
const highlightNoteTip = document.getElementById('highlightNoteTip');
const onboardingOverlay = document.getElementById('onboardingOverlay');
const onboardingNext = document.getElementById('onboardingNext');
const onboardingSkip = document.getElementById('onboardingSkip');
const translateBanner = document.getElementById('translateBanner');
const searchBar = document.getElementById('searchBar');
const searchInput = document.getElementById('searchInput');
const searchStatus = document.getElementById('searchStatus');
const searchPrev = document.getElementById('searchPrev');
const searchNext = document.getElementById('searchNext');
const closeSearch = document.getElementById('closeSearch');
const toggleSearch = document.getElementById('toggleSearch');
const bookmarksPanel = document.getElementById('bookmarksPanel');
const bookmarksList = document.getElementById('bookmarksList');
const toggleBookmarks = document.getElementById('toggleBookmarks');
const closeBookmarks = document.getElementById('closeBookmarks');
const addBookmarkBtn = document.getElementById('addBookmarkBtn');
const shortcutsOverlay = document.getElementById('shortcutsOverlay');
const closeShortcuts = document.getElementById('closeShortcuts');
const progressClickArea = document.getElementById('progressClickArea');
const chapterNav = document.getElementById('chapterNav');
const prevChapterBtn = document.getElementById('prevChapterBtn');
const nextChapterBtn = document.getElementById('nextChapterBtn');
const chapterNavLabel = document.getElementById('chapterNavLabel');
const chapterNavTitle = document.getElementById('chapterNavTitle');

let activeWord = '';
let activeWordData = null;
let activeWordEl = null;
let currentDoc = null;
let currentBlocks = [];
let currentHighlights = [];
let currentNotes = [];
let activeBlockIdx = -1;
let savedWords = new Set();
let readEventSource = null;
let progressSaveTimer = null;
let scrollObserver = null;
let fontSize = parseInt(localStorage.getItem('readerFontSize') || '18', 10);
let ttsEnabled = false;
let pendingSelection = null;
let pendingHighlightId = null;
let vocabDueCount = 0;
let onboardingStep = 1;
let activeHighlightAnchor = null;
let pendingHighlightColor = localStorage.getItem('readerHighlightColor') || 'yellow';
let sseRetryCount = 0;
let sseRetryTimer = null;
let toastTimer = null;
let activeLookupSeq = 0;
let manualSelect = false;
const CHAPTER_CHUNK = 80;
let lazyRenderedUntil = 0;
let totalBlockCount = 0;
let loadedBlockCount = 0;
let chapters = [];
let currentChapterIndex = 0;
let currentChapter = null;
let chapterBlockTotal = 0;
let chapterLoadedOffset = 0;
let chapterRenderFrom = 0;
let chapterRenderTo = 0;
let lastRenderedSection = null;
let lazyScrollHandler = null;
let currentBookmarks = [];
let searchHits = [];
let searchHitIndex = -1;
let searchDebounceTimer = null;
const READER_THEME_PREF_KEY = 'readerThemeExplicitV1';

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

function showToast(msg, type = '') {
  statusMsg.textContent = msg;
  statusMsg.className = 'reader-toast' + (type ? ` ${type}` : '');
  statusMsg.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => statusMsg.classList.add('hidden'), 2800);
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function zhSkeleton() {
  return `<div class="zh-skeleton"><span></span><span></span><span></span></div>`;
}

function wrapWords(text) {
  return text.split(/(\s+)/).map((part) => {
    if (!part.trim()) return part;
    const clean = part.replace(/[^A-Za-z'-]/g, '');
    if (!clean) return escapeHtml(part);
    const lookupWord = clean.split("'")[0].replace(/[^A-Za-z]/g, '').toLowerCase();
    if (!lookupWord) return escapeHtml(part);
    const saved = savedWords.has(lookupWord) ? ' saved-word' : '';
    return `<span class="clickable-word${saved}" data-word="${lookupWord}">${escapeHtml(part)}</span>`;
  }).join('');
}

function renderEnText(text, blockId, blockIdx) {
  const hit = searchHits[searchHitIndex];
  const q = searchInput?.value.trim();
  const hls = currentHighlights.filter((h) => h.block_id === blockId);
  const isCurrentSearch = hit && hit.order_index === blockIdx && q && !hls.length;

  if (isCurrentSearch) {
    const pos = text.toLowerCase().indexOf(q.toLowerCase(), Math.max(0, hit.match_start - 1));
    if (pos >= 0) {
      return wrapWords(text.slice(0, pos))
        + `<mark class="search-term">${escapeHtml(text.slice(pos, pos + q.length))}</mark>`
        + wrapWords(text.slice(pos + q.length));
    }
  }

  if (!hls.length) return wrapWords(text);
  const sorted = [...hls].sort((a, b) => a.start_offset - b.start_offset);
  const nonOverlap = sorted.filter((h, i) => i === 0 || h.start_offset >= sorted[i - 1].end_offset);
  let html = '';
  let last = 0;
  for (const h of nonOverlap) {
    if (h.start_offset > last) html += wrapWords(text.slice(last, h.start_offset));
    html += `<mark class="user-highlight hl-${h.color || 'yellow'}" data-hl="${h.id}">${wrapWords(text.slice(h.start_offset, h.end_offset))}</mark>`;
    last = h.end_offset;
  }
  if (last < text.length) html += wrapWords(text.slice(last));
  return html;
}

function updateTranslateBanner() {
  if (!translateBanner || !currentDoc) return;
  const st = currentDoc.translate_status;
  if (st === 'done') {
    const msg = currentDoc.status_message || '';
    const partialFail = msg.includes('未译出') || msg.includes('段失败') || msg.includes('暂未译出');
    if (partialFail) {
      document.body.classList.add('has-translate-banner');
      translateBanner.className = 'reader-translate-banner translating';
      translateBanner.innerHTML = `
        <span>ℹ️ 当前书籍已可阅读，${escapeHtml(msg.replace('可重试', '可稍后重试'))}</span>
        <button id="retryTranslateBtn" class="btn-secondary btn-sm">补译未译段落</button>
      `;
      translateBanner.classList.remove('hidden');
      document.getElementById('retryTranslateBtn')?.addEventListener('click', retryTranslate);
      return;
    }
    translateBanner.classList.add('hidden');
    document.body.classList.remove('has-translate-banner');
    return;
  }
  document.body.classList.add('has-translate-banner');
  if (st === 'failed') {
    translateBanner.className = 'reader-translate-banner failed';
    translateBanner.innerHTML = `
      <span>⚠️ ${escapeHtml(currentDoc.status_message || '翻译未完成，可先读英文')}</span>
      <button id="retryTranslateBtn" class="btn-secondary btn-sm">补译未译段落</button>
    `;
    translateBanner.classList.remove('hidden');
    document.getElementById('retryTranslateBtn')?.addEventListener('click', retryTranslate);
    return;
  }
  if (st === 'ready') {
    const total = currentDoc.block_count || 0;
    const hint = total > 500
      ? '大型书籍已导入，采用按需翻译：打开章节后自动翻译，可先读英文'
      : '按需翻译：切换章节后自动翻译当前章，可先读英文';
    translateBanner.className = 'reader-translate-banner ready';
    translateBanner.innerHTML = `<span>📖 ${escapeHtml(hint)}</span>`;
    translateBanner.classList.remove('hidden');
    return;
  }
  translateBanner.className = 'reader-translate-banner translating';
  const msg = currentDoc.status_message || '';
  const detail = msg.includes('已译') || msg.includes('约还需')
    ? msg
    : `翻译中 ${currentDoc.translate_progress || 0}% · 可先读英文，译文将自动出现`;
  translateBanner.innerHTML = `<span>🔄 ${escapeHtml(detail)}</span>`;
  translateBanner.classList.remove('hidden');
}

async function retryTranslate() {
  try {
    const resp = await api(`/api/readings/${docId}/translate`, { method: 'POST' });
    if (currentDoc) {
      if (resp.queued === false) {
        currentDoc.translate_status = 'done';
        currentDoc.status_message = '翻译已完成';
        updateTranslateBanner();
        showToast('所有段落均已翻译', 'success');
        return;
      }
      currentDoc.translate_status = 'translating';
      currentDoc.status_message = '补译未翻译段落...';
      if (resp.translated_blocks != null) {
        currentDoc.translated_blocks = resp.translated_blocks;
        currentDoc.translate_progress = Math.min(
          100,
          Math.round((resp.translated_blocks / Math.max(currentDoc.block_count || 1, 1)) * 100),
        );
      }
    }
    sseRetryCount = 0;
    startTranslationStream();
    updateTranslateBanner();
    showToast('已开始补译未译段落', 'success');
  } catch (e) {
    showToast('补译失败: ' + e.message, 'error');
  }
}

function scheduleSseReconnect() {
  if (!currentDoc || ['done', 'failed', 'ready'].includes(currentDoc.translate_status)) return;
  clearTimeout(sseRetryTimer);
  const delay = Math.min(30000, 1000 * Math.pow(2, sseRetryCount));
  sseRetryTimer = setTimeout(() => {
    sseRetryCount += 1;
    startTranslationStream(true);
  }, delay);
}

function goToNote(note) {
  if (!note) return;
  void jumpToBlockIndex(note.block_index, note.block_id, note.highlight_id);
}

async function jumpToBlockIndex(blockIndex, blockId, highlightId) {
  let idx = blockIndex;
  if (idx == null && blockId != null) {
    const loaded = currentBlocks.find((b) => b && b.id === blockId);
    idx = loaded?.order_index;
  }
  if (idx == null && highlightId) {
    const hl = currentHighlights.find((h) => h.id === highlightId);
    if (hl) {
      const loaded = currentBlocks.find((b) => b && b.id === hl.block_id);
      idx = loaded?.order_index;
    }
  }
  if (idx == null) return;
  await gotoBlockIndex(idx);
  if (highlightId) {
    const mark = blockList.querySelector(`mark[data-hl="${highlightId}"]`);
    if (mark) {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
      handleHighlightClick(highlightId, mark);
    }
  }
}

function applyTheme(nextTheme = '', persistExplicit = false) {
  const savedTheme = localStorage.getItem('readerTheme');
  const hasExplicitTheme = localStorage.getItem(READER_THEME_PREF_KEY) === '1';
  const theme = nextTheme || (hasExplicitTheme ? savedTheme : 'sepia') || 'sepia';
  document.body.classList.remove('theme-light', 'theme-sepia');
  if (theme === 'light') document.body.classList.add('theme-light');
  else if (theme === 'sepia') document.body.classList.add('theme-sepia');
  if (readerTheme) readerTheme.value = theme;
  localStorage.setItem('readerTheme', theme);
  if (persistExplicit) localStorage.setItem(READER_THEME_PREF_KEY, '1');
}

function updateVocabStatsUI(stats) {
  if (!vocabStatsBar || !vocabStatsText) return;
  const count = stats?.word_count ?? savedWords.size;
  vocabDueCount = stats?.due_count ?? 0;
  if (count > 0) {
    vocabStatsBar.classList.remove('hidden');
    const duePart = vocabDueCount > 0 ? `，${vocabDueCount} 个待复习` : '';
    vocabStatsText.textContent = `本文 ${count} 生词${duePart}`;
    if (vocabReviewLink) {
      vocabReviewLink.href = `/vocab?video=reading-${docId}`;
      vocabReviewLink.textContent = vocabDueCount > 0 ? '去复习' : '查看生词';
    }
    if (vocabStatsBar.querySelector('#vocabPracticeLink')) {
      vocabStatsBar.querySelector('#vocabPracticeLink').href = `/vocab?video=reading-${docId}#practiceSection`;
    } else {
      const linksWrap = vocabStatsBar.querySelector('.reader-vocab-links') || vocabStatsBar;
      const practiceLink = document.createElement('a');
      practiceLink.id = 'vocabPracticeLink';
      practiceLink.className = 'reader-vocab-link reader-vocab-link--ghost';
      practiceLink.href = `/vocab?video=reading-${docId}#practiceSection`;
      practiceLink.textContent = '去练习';
      linksWrap.appendChild(practiceLink);
    }
  } else {
    vocabStatsBar.classList.add('hidden');
  }
}

function notesByHighlightId() {
  const map = new Map();
  currentNotes.forEach((n) => {
    if (n.highlight_id) map.set(n.highlight_id, n);
  });
  return map;
}

function applyDisplayMode() {
  blockList.className = `reading-flow mode-${displayMode.value}`;
  localStorage.setItem('readerDisplayMode', displayMode.value);
}

function applyFontSize() {
  blockList.style.setProperty('--reader-font-size', fontSize + 'px');
  if (fontSizeLabel) fontSizeLabel.textContent = fontSize;
  localStorage.setItem('readerFontSize', String(fontSize));
}

function updateProgressUI(blockIndex) {
  if (!currentDoc || !currentDoc.block_count) return;
  const pct = Math.min(100, Math.round(((blockIndex + 1) / currentDoc.block_count) * 100));
  readProgressFill.style.width = `${pct}%`;
  if (chapters.length && currentChapter) {
    const withinChapter = Math.max(1, blockIndex - currentChapter.start_block + 1);
    readProgressText.textContent = `第 ${currentChapterIndex + 1} / ${chapters.length} 章 · 本章 ${withinChapter} / ${currentChapter.block_count} 段`;
    if (chapterNavLabel) chapterNavLabel.textContent = `第 ${currentChapterIndex + 1} / ${chapters.length} 章`;
    return;
  }
  readProgressText.textContent = `${blockIndex + 1} / ${currentDoc.block_count} 段`;
}

function scheduleSaveProgress(blockIndex) {
  clearTimeout(progressSaveTimer);
  progressSaveTimer = setTimeout(async () => {
    try {
      currentDoc = await api(`/api/readings/${docId}/progress`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ block_index: blockIndex }),
      });
    } catch (_) {}
  }, 800);
}

function setupScrollObserver() {
  if (scrollObserver) scrollObserver.disconnect();
  scrollObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && entry.intersectionRatio >= 0.45) {
          const idx = parseInt(entry.target.dataset.index, 10);
          if (idx >= 0) {
            if (!manualSelect) {
              highlightBlock(idx);
            }
            scheduleSaveProgress(idx);
            if (ttsEnabled) speakBlock(idx);
          }
        }
      });
    },
    { threshold: [0.45], rootMargin: '-12% 0px -45% 0px' }
  );
  blockList.querySelectorAll('.reading-block').forEach((el) => scrollObserver.observe(el));
}

function highlightBlock(idx) {
  activeBlockIdx = idx;
  blockList.querySelectorAll('.reading-block').forEach((el) => {
    const elIdx = parseInt(el.dataset.index, 10);
    if (elIdx === idx) {
      el.classList.add('active');
    } else {
      el.classList.remove('active');
    }
  });
  tocList?.querySelectorAll('.toc-chapter, .toc-item').forEach((el) => {
    if (el.classList.contains('toc-chapter')) {
      const chapterIndex = parseInt(el.dataset.chapter, 10);
      el.classList.toggle('active', chapterIndex === currentChapterIndex);
      return;
    }
    const itemIdx = parseInt(el.dataset.toc, 10);
    if (!Number.isNaN(itemIdx)) {
      el.classList.toggle('active', itemIdx === activeBlockIdx);
    }
  });
  updateProgressUI(idx);
}

function applyTranslationToBlock(orderIndex, translation, forceUpdate = false) {
  if (!currentBlocks[orderIndex]) return;
  const prev = currentBlocks[orderIndex].translation;
  currentBlocks[orderIndex].translation = translation;
  const el = blockList.querySelector(`.reading-block[data-index="${orderIndex}"]`);
  if (!el) return;
  const zh = el.querySelector('.reading-text-zh');
  if (!zh) return;
  const shouldUpdate = forceUpdate || !zh.classList.contains('zh-loaded') || prev !== translation;
  if (!shouldUpdate) return;
  if (translation) {
    zh.innerHTML = escapeHtml(translation);
    zh.classList.add('zh-loaded', 'zh-fade-in');
  } else {
    zh.innerHTML = zhSkeleton();
    zh.classList.remove('zh-loaded');
  }
}

function chapterForBlockIndex(blockIndex) {
  for (let i = 0; i < chapters.length; i += 1) {
    const chapter = chapters[i];
    if (blockIndex >= chapter.start_block && blockIndex <= chapter.end_block) {
      return i;
    }
  }
  return 0;
}

function getChapterRange() {
  if (!currentChapter) {
    return { start: 0, end: Math.max(0, totalBlockCount - 1) };
  }
  return { start: currentChapter.start_block, end: currentChapter.end_block };
}

function updateChapterNav() {
  if (!chapterNav) return;
  if (!chapters.length) {
    chapterNav.classList.add('hidden');
    return;
  }
  chapterNav.classList.remove('hidden');
  if (chapterNavLabel) {
    chapterNavLabel.textContent = `第 ${currentChapterIndex + 1} / ${chapters.length} 章`;
  }
  if (chapterNavTitle) {
    const title = currentChapter?.title || '';
    const count = currentChapter?.block_count || chapterBlockTotal || 0;
    chapterNavTitle.textContent = title ? `${title} · ${count} 段` : `${count} 段`;
  }
  if (prevChapterBtn) prevChapterBtn.disabled = currentChapterIndex <= 0;
  if (nextChapterBtn) nextChapterBtn.disabled = currentChapterIndex >= chapters.length - 1;
}

function updateProgressMeta() {
  if (!readProgressText) return;
  if (chapters.length && currentChapter) {
    readProgressText.textContent = `第 ${currentChapterIndex + 1} / ${chapters.length} 章 · ${currentChapter.title || '未命名'}`;
    return;
  }
  readProgressText.textContent = currentDoc?.block_count
    ? `${Math.max(1, (currentDoc.last_block_index || 0) + 1)} / ${currentDoc.block_count} 段`
    : '0 / 0 段';
}

function buildChapters() {
  return chapters;
}

function renderToc() {
  if (!tocList) return;
  
  // 添加hover管理，确保同时只高亮一个
  const addHoverListeners = (items) => {
    items.forEach((btn) => {
      btn.addEventListener('mouseenter', () => {
        // hover时，移除其他所有active
        items.forEach((item) => item.classList.remove('active'));
      });
      btn.addEventListener('mouseleave', () => {
        // 离开时恢复active状态
        renderToc();
      });
    });
  };

  if (chapters.length) {
    tocList.innerHTML = chapters.map((ch) => `
      <button class="toc-chapter${currentChapterIndex === ch.chapter_index ? ' active' : ''}"
        data-chapter="${ch.chapter_index}">
        <span class="toc-chapter-title">${escapeHtml(ch.title)}</span>
        <span class="toc-chapter-range">${ch.block_count} 段 · 全书第 ${ch.start_block + 1}–${ch.end_block + 1} 段</span>
      </button>
    `).join('');
    const buttons = tocList.querySelectorAll('.toc-chapter');
    buttons.forEach((btn) => {
      btn.addEventListener('click', async () => {
        await loadChapter(parseInt(btn.dataset.chapter, 10));
      });
    });
    addHoverListeners(buttons);
    return;
  }
  tocList.innerHTML = currentBlocks.map((b, i) => {
    if (!b) return '';
    const preview = b.text.slice(0, 60).replace(/\s+/g, ' ') + (b.text.length > 60 ? '…' : '');
    const hasZh = !!b.translation;
    return `<button class="toc-item${i === activeBlockIdx ? ' active' : ''}" data-toc="${i}">
      <span class="toc-num">${i + 1}</span>
      <span class="toc-preview">${escapeHtml(preview)}</span>
      ${hasZh ? '' : '<span class="toc-pending">译</span>'}
    </button>`;
  }).join('');
  const buttons = tocList.querySelectorAll('.toc-item');
  buttons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const idx = parseInt(btn.dataset.toc, 10);
      await gotoBlockIndex(idx);
    });
  });
  addHoverListeners(buttons);
}

function createBlockElement(block, idx) {
  const item = document.createElement('section');
  item.className = 'reading-block';
  item.dataset.index = idx;
  const noteMap = notesByHighlightId();
  item.innerHTML = `
    <div class="reading-block-gutter" aria-hidden="true"></div>
    <div class="reading-block-inner">
      <div class="reading-text-en">${renderEnText(block.text, block.id, idx)}</div>
      <div class="reading-text-zh ${block.translation ? 'zh-loaded' : ''}">${block.translation ? escapeHtml(block.translation) : zhSkeleton()}</div>
    </div>
    <div class="reading-block-actions">
      <button class="reading-action-btn" data-speak="${idx}" title="朗读">🔊</button>
      <button class="reading-action-btn" data-note="${idx}" title="记笔记">📝</button>
    </div>
  `;
  
  
  
  item.querySelector('[data-speak]').addEventListener('click', (e) => { e.stopPropagation(); speakBlock(idx); });
  item.querySelector('[data-note]').addEventListener('click', (e) => {
    e.stopPropagation();
    activeBlockIdx = idx;
    pendingHighlightId = null;
    notesPanel.classList.remove('hidden');
    document.body.classList.add('side-open');
    newNoteText.focus();
  });
  item.querySelectorAll('mark.user-highlight').forEach((mark) => {
    const hlId = parseInt(mark.dataset.hl, 10);
    if (noteMap.has(hlId)) mark.classList.add('has-note');
    mark.addEventListener('click', (e) => {
      e.stopPropagation();
      handleHighlightClick(hlId, mark);
    });
  });
  item.addEventListener('click', (e) => {
    const wordEl = e.target.closest('.clickable-word');
    manualSelect = true;
    activeBlockIdx = idx;
    highlightBlock(idx);
    if (wordEl) {
      e.stopPropagation();
      loadWord(wordEl.dataset.word, wordEl);
    }
  });
  return item;
}

function appendBlocksRange(fromIdx, toIdx) {
  for (let idx = fromIdx; idx < toIdx; idx++) {
    const block = currentBlocks[idx];
    if (!block) continue;
    if (block.section_title && block.section_title !== lastRenderedSection) {
      const heading = document.createElement('h2');
      heading.className = 'reading-section-title';
      heading.textContent = block.section_title;
      heading.dataset.sectionStart = idx;
      blockList.appendChild(heading);
      lastRenderedSection = block.section_title;
    }
    const el = createBlockElement(block, idx);
    blockList.appendChild(el);
    scrollObserver?.observe(el);
  }
  lazyRenderedUntil = toIdx;
}

function updateLazyLoadSentinel() {
  let sentinel = document.getElementById('lazyLoadSentinel');
  const { end } = getChapterRange();
  const chapterEnd = end + 1;
  if (lazyRenderedUntil >= chapterEnd && chapterLoadedOffset >= chapterBlockTotal) {
    sentinel?.remove();
    return;
  }
  if (!sentinel) {
    sentinel = document.createElement('div');
    sentinel.id = 'lazyLoadSentinel';
    sentinel.className = 'lazy-load-sentinel';
    blockList.appendChild(sentinel);
  } else {
    blockList.appendChild(sentinel);
  }
  const shown = Math.max(0, lazyRenderedUntil - chapterRenderFrom);
  if (lazyRenderedUntil < chapterEnd || chapterLoadedOffset < chapterBlockTotal) {
    sentinel.textContent = `本章已显示 ${shown} / ${chapterBlockTotal} 段，继续向下滚动加载…`;
    return;
  }
  if (currentChapterIndex < chapters.length - 1) {
    sentinel.innerHTML = `本章已读完。<button type="button" class="btn-primary btn-sm" id="loadNextChapterBtn">进入下一章 →</button>`;
    sentinel.querySelector('#loadNextChapterBtn')?.addEventListener('click', () => {
      loadChapter(currentChapterIndex + 1);
    });
    return;
  }
  sentinel.textContent = '已读至全书末尾';
}

function setupLazyScrollLoader() {
  if (lazyScrollHandler) window.removeEventListener('scroll', lazyScrollHandler);
  lazyScrollHandler = () => {
    const { end } = getChapterRange();
    const chapterEnd = end + 1;
    if (lazyRenderedUntil >= chapterEnd && chapterLoadedOffset >= chapterBlockTotal) return;
    const nearBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 900;
    if (!nearBottom) return;
    (async () => {
      if (lazyRenderedUntil < chapterEnd) {
        await ensureChapterBlocksLoaded(lazyRenderedUntil);
        const nextEnd = Math.min(chapterEnd, lazyRenderedUntil + CHAPTER_CHUNK);
        appendBlocksRange(lazyRenderedUntil, nextEnd);
      } else if (chapterLoadedOffset < chapterBlockTotal) {
        await ensureChapterBlocksLoaded(end);
        const nextEnd = Math.min(chapterEnd, lazyRenderedUntil + CHAPTER_CHUNK);
        appendBlocksRange(lazyRenderedUntil, nextEnd);
      }
      updateLazyLoadSentinel();
      if (chapterLoadedOffset < chapterBlockTotal) {
        prefetchChapterBlocks(currentChapterIndex, chapterLoadedOffset);
      }
    })();
  };
  window.addEventListener('scroll', lazyScrollHandler, { passive: true });
}

async function ensureBlockRendered(idx) {
  await ensureChapterBlocksLoaded(idx);
  const { end } = getChapterRange();
  if (idx < lazyRenderedUntil) return;
  const chapterEnd = end + 1;
  const nextEnd = Math.min(chapterEnd, Math.max(idx + 25, lazyRenderedUntil + CHAPTER_CHUNK));
  appendBlocksRange(lazyRenderedUntil, nextEnd);
  updateLazyLoadSentinel();
}

function refreshBlockAt(idx) {
  ensureBlockRendered(idx);
  const old = blockList.querySelector(`.reading-block[data-index="${idx}"]`);
  if (!old) return;
  const newEl = createBlockElement(currentBlocks[idx], idx);
  if (old.classList.contains('active')) {
    newEl.classList.add('active');
  }
  old.replaceWith(newEl);
  scrollObserver?.observe(newEl);
}

function refreshAllRenderedBlocks() {
  for (let i = 0; i < lazyRenderedUntil; i++) refreshBlockAt(i);
}

function renderBlocks(blocks, fullRender = true) {
  const { start, end } = getChapterRange();
  chapterRenderFrom = start;
  chapterRenderTo = end;
  const chapterEnd = end + 1;
  if (fullRender || !blockList.querySelector('.reading-block')) {
    blockList.innerHTML = '';
    lastRenderedSection = null;
    lazyRenderedUntil = start;
    const initialEnd = Math.min(chapterEnd, start + CHAPTER_CHUNK);
    appendBlocksRange(start, initialEnd);
    applyDisplayMode();
    applyFontSize();
    setupScrollObserver();
    setupLazyScrollLoader();
    renderToc();
    updateChapterNav();
    updateLazyLoadSentinel();
    return;
  }
  blocks.forEach((block, idx) => {
    if (!block) return;
    const el = blockList.querySelector(`.reading-block[data-index="${idx}"]`);
    if (!el) return;
    const zh = el.querySelector('.reading-text-zh');
    if (block.translation && zh && !zh.classList.contains('zh-loaded')) {
      zh.innerHTML = escapeHtml(block.translation);
      zh.classList.add('zh-loaded', 'zh-fade-in');
    }
  });
}

function mergeBlocks(incoming) {
  if (!incoming.length) return false;
  let changed = false;
  incoming.forEach((b, i) => {
    if (!currentBlocks[i]) {
      currentBlocks[i] = b;
      changed = true;
    } else {
      if (b.translation !== currentBlocks[i].translation) {
        currentBlocks[i].translation = b.translation;
        changed = true;
      }
      if (b.section_title && !currentBlocks[i].section_title) {
        currentBlocks[i].section_title = b.section_title;
        changed = true;
      }
    }
  });
  return changed;
}

function refreshSavedWordHighlights() {
  blockList.querySelectorAll('.clickable-word').forEach((el) => {
    el.classList.toggle('saved-word', savedWords.has(el.dataset.word));
  });
}

function scrollToBlock(idx) {
  (async () => {
    if (chapters.length && chapterForBlockIndex(idx) !== currentChapterIndex) {
      await gotoBlockIndex(idx);
      return;
    }
    await ensureBlockRendered(idx);
    const el = blockList.querySelector(`.reading-block[data-index="${idx}"]`);
    if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
  })();
}

function jumpToProgress(pct) {
  if (!currentDoc?.block_count) return;
  const idx = Math.min(currentDoc.block_count - 1, Math.max(0, Math.floor(pct * currentDoc.block_count)));
  highlightBlock(idx);
  scrollToBlock(idx);
  scheduleSaveProgress(idx);
}

function defaultBookmarkLabel(blockIndex) {
  const block = currentBlocks[blockIndex];
  if (!block) return `第 ${blockIndex + 1} 段`;
  if (block.section_title) return block.section_title;
  const preview = block.text.slice(0, 40).replace(/\s+/g, ' ').trim();
  return preview ? preview + (block.text.length > 40 ? '…' : '') : `第 ${blockIndex + 1} 段`;
}

function renderBookmarks() {
  if (!bookmarksList) return;
  if (!currentBookmarks.length) {
    bookmarksList.innerHTML = '<p class="notes-empty">暂无书签，阅读时按 <kbd>B</kbd> 或点击上方按钮添加</p>';
    return;
  }
  bookmarksList.innerHTML = currentBookmarks.map((bm) => {
    const block = currentBlocks[bm.block_index];
    const sub = block?.section_title ? escapeHtml(block.section_title) : `第 ${bm.block_index + 1} 段`;
    return `
      <div class="bookmark-item" data-bm-id="${bm.id}">
        <button class="bookmark-goto" data-goto-bm="${bm.block_index}">
          <span class="bookmark-label">${escapeHtml(bm.label || defaultBookmarkLabel(bm.block_index))}</span>
          <span class="bookmark-meta">${sub}</span>
        </button>
        <button class="btn-danger btn-sm" data-del-bm="${bm.id}" title="删除">✕</button>
      </div>`;
  }).join('');
  bookmarksList.querySelectorAll('[data-goto-bm]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const idx = parseInt(btn.dataset.gotoBm, 10);
      await gotoBlockIndex(idx);
    });
  });
  bookmarksList.querySelectorAll('[data-del-bm]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      try {
        await api(`/api/readings/${docId}/bookmarks/${btn.dataset.delBm}`, { method: 'DELETE' });
        currentBookmarks = currentBookmarks.filter((b) => String(b.id) !== btn.dataset.delBm);
        renderBookmarks();
        showToast('书签已删除', 'success');
      } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
      }
    });
  });
}

async function addBookmarkAtCurrent() {
  const idx = activeBlockIdx >= 0 ? activeBlockIdx : (currentDoc?.last_block_index || 0);
  if (!currentBlocks.length) return;
  const label = defaultBookmarkLabel(idx);
  try {
    const bm = await api(`/api/readings/${docId}/bookmarks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ block_index: idx, label }),
    });
    currentBookmarks.push(bm);
    currentBookmarks.sort((a, b) => a.block_index - b.block_index);
    renderBookmarks();
    showToast(`已添加书签：${label}`, 'success');
  } catch (e) {
    showToast('添加书签失败: ' + e.message, 'error');
  }
}

function openSearchBar() {
  searchBar?.classList.remove('hidden');
  document.body.classList.add('has-search-bar');
  searchInput?.focus();
  searchInput?.select();
}

function closeSearchBar() {
  searchBar?.classList.add('hidden');
  document.body.classList.remove('has-search-bar');
  searchHits = [];
  searchHitIndex = -1;
  if (searchStatus) searchStatus.textContent = '';
  refreshAllRenderedBlocks();
  blockList.querySelectorAll('.reading-block.search-hit, .reading-block.search-current').forEach((el) => {
    el.classList.remove('search-hit', 'search-current');
  });
}

async function runSearch(query) {
  const q = (query || '').trim();
  if (q.length < 2) {
    searchHits = [];
    searchHitIndex = -1;
    if (searchStatus) searchStatus.textContent = '至少输入 2 个字符';
    return;
  }
  try {
    searchHits = await api(`/api/readings/${docId}/search?q=${encodeURIComponent(q)}&limit=100`);
    searchHitIndex = searchHits.length ? 0 : -1;
    if (searchStatus) {
      searchStatus.textContent = searchHits.length
        ? `${searchHitIndex + 1} / ${searchHits.length}`
        : '无结果';
    }
    highlightSearchHit();
  } catch (e) {
    if (searchStatus) searchStatus.textContent = '搜索失败';
  }
}

function highlightSearchHit() {
  blockList.querySelectorAll('.reading-block').forEach((el) => {
    el.classList.remove('search-hit', 'search-current');
  });
  const hitIndices = new Set(searchHits.map((h) => h.order_index));
  hitIndices.forEach((idx) => {
    ensureBlockRendered(idx);
    blockList.querySelector(`.reading-block[data-index="${idx}"]`)?.classList.add('search-hit');
  });
  const cur = searchHits[searchHitIndex];
  if (!cur) {
    if (searchHits.length === 0) refreshAllRenderedBlocks();
    return;
  }
  searchHits.forEach((h) => {
    if (blockList.querySelector(`.reading-block[data-index="${h.order_index}"]`)) {
      refreshBlockAt(h.order_index);
    }
  });
  const el = blockList.querySelector(`.reading-block[data-index="${cur.order_index}"]`);
  if (el) {
    el.classList.add('search-current');
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  if (searchStatus && searchHits.length) {
    searchStatus.textContent = `${searchHitIndex + 1} / ${searchHits.length}`;
  }
}

function gotoSearchHit(delta) {
  if (!searchHits.length) return;
  searchHitIndex = (searchHitIndex + delta + searchHits.length) % searchHits.length;
  highlightSearchHit();
}

function showShortcuts() {
  shortcutsOverlay?.classList.remove('hidden');
}

function hideShortcuts() {
  shortcutsOverlay?.classList.add('hidden');
}

function closeAllOverlays() {
  hidePopover();
  hideShortcuts();
  closeSearchBar();
  selectionToolbar?.classList.add('hidden');
  highlightNoteTip?.classList.add('hidden');
  settingsPanel?.classList.add('hidden');
}


function positionPopover(anchorEl) {
  const rect = anchorEl.getBoundingClientRect();
  const popW = 300;
  let left = rect.left + rect.width / 2 - popW / 2;
  left = Math.max(12, Math.min(left, window.innerWidth - popW - 12));
  let top = rect.bottom + 8;
  if (top + 220 > window.innerHeight) top = rect.top - 8 - 200;
  wordPopover.style.left = `${left}px`;
  wordPopover.style.top = `${top + window.scrollY}px`;
}

function hidePopover() {
  wordPopover.classList.add('hidden');
  activeWordEl = null;
}

function lookupSourceLabel(source) {
  const map = {
    wordbook: '词书',
    vocab: '生词缓存',
    'online-cache': '本地缓存',
    core_en: '内置词典',
    miss: '本地未命中',
  };
  return map[source] || source || '本地词典';
}

function renderWordSuggestions(data) {
  const items = Array.isArray(data?.suggestions) ? data.suggestions : [];
  if (!items.length) return '';
  return `
    <div class="word-popover-suggestions">
      <strong>近似词</strong>
      <div class="word-popover-suggestion-list">
        ${items.map((item) => `<button type="button" class="word-suggestion-chip" data-suggest-word="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join('')}
      </div>
    </div>
  `;
}

function renderPopoverCompact(data) {
  const saved = savedWords.has((data.word || '').toLowerCase());
  const zh = data.translation || data.youdao_translation || data.definition || '暂无本地释义';
  wordPopoverBody.innerHTML = `
    <div class="word-popover-word-row">
      <div class="word-popover-word">${escapeHtml(data.word)}</div>
      <span class="word-popover-source">${escapeHtml(lookupSourceLabel(data.lookup_source))}</span>
    </div>
    <div class="word-popover-phonetic">${escapeHtml(data.pronunciation || '')}</div>
    <div class="word-popover-def">${escapeHtml(zh)}</div>
    ${data.definition && data.definition !== zh
      ? `<div class="word-popover-alt">英文释义: ${escapeHtml(data.definition)}</div>` : ''}
    <div class="word-popover-hint">本次查词已命中本地词典，未使用在线翻译。</div>
    ${renderWordSuggestions(data)}
  `;
  saveWordBtn.textContent = saved ? '★ 已收藏' : '⭐ 收藏';
  saveWordBtn.disabled = saved;
  expandWordBtn.classList.remove('hidden');
}

function renderPopoverExpanded(data) {
  wordPopoverBody.innerHTML = `
    <div class="word-popover-word-row">
      <div class="word-popover-word">${escapeHtml(data.word)}</div>
      <span class="word-popover-source">${escapeHtml(lookupSourceLabel(data.lookup_source))}</span>
    </div>
    <div class="word-popover-phonetic">${escapeHtml(data.pronunciation || '')}</div>
    <div class="word-popover-detail">
      <div><strong>中文释义</strong> ${escapeHtml(data.translation || data.youdao_translation || '暂无')}</div>
      <div><strong>英文释义</strong> ${escapeHtml(data.definition || '暂无')}</div>
      ${data.part_of_speech ? `<div><strong>词性</strong> ${escapeHtml(data.part_of_speech)}</div>` : ''}
      ${data.example ? `<div><strong>例句</strong> ${escapeHtml(data.example)}</div>` : ''}
    </div>
    <div class="word-popover-hint">本次查词已命中本地词典，未使用在线翻译。</div>
    ${renderWordSuggestions(data)}
  `;
}

async function fetchChapterBlocksPage(chapterIndex, offset, limit = CHAPTER_CHUNK) {
  const page = await api(`/api/readings/${docId}/chapters/${chapterIndex}/blocks?offset=${offset}&limit=${limit}`);
  page.items.forEach((b) => {
    currentBlocks[b.order_index] = b;
  });
  chapterLoadedOffset = Math.max(chapterLoadedOffset, offset + page.items.length);
  loadedBlockCount = Math.max(loadedBlockCount, chapterLoadedOffset + (currentChapter?.start_block || 0));
  return page;
}

function prefetchChapterBlocks(chapterIndex, offset) {
  fetchChapterBlocksPage(chapterIndex, offset, CHAPTER_CHUNK).catch(() => {});
}

async function ensureChapterBlocksLoaded(upToIndex) {
  if (!currentChapter) return;
  const need = Math.min(chapterBlockTotal, upToIndex - currentChapter.start_block + CHAPTER_CHUNK);
  while (chapterLoadedOffset < need && chapterLoadedOffset < chapterBlockTotal) {
    await fetchChapterBlocksPage(currentChapterIndex, chapterLoadedOffset, CHAPTER_CHUNK);
  }
}

async function loadChapter(chapterIndex, { scrollTop = true, restoreBlock = null } = {}) {
  if (!chapters.length) return;
  const safeIndex = Math.max(0, Math.min(chapterIndex, chapters.length - 1));
  hidePopover();
  const page = await api(`/api/readings/${docId}/chapters/${safeIndex}/blocks?offset=0&limit=${CHAPTER_CHUNK}`);
  currentChapterIndex = safeIndex;
  currentChapter = page.chapter;
  chapterBlockTotal = page.total;
  chapterLoadedOffset = page.items.length;
  page.items.forEach((b) => {
    currentBlocks[b.order_index] = b;
  });
  if (page.has_more) prefetchChapterBlocks(safeIndex, chapterLoadedOffset);
  renderBlocks(currentBlocks, true);
  updateChapterNav();
  updateProgressMeta();
  requestChapterTranslation(safeIndex);
  startTranslationStream();
  if (restoreBlock != null) {
    await ensureBlockRendered(restoreBlock);
    highlightBlock(restoreBlock);
    scrollToBlock(restoreBlock);
    scheduleSaveProgress(restoreBlock);
    return;
  }
  const targetBlock = currentChapter.start_block;
  highlightBlock(targetBlock);
  if (scrollTop) window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function gotoBlockIndex(idx) {
  const chapterIndex = chapterForBlockIndex(idx);
  if (chapterIndex !== currentChapterIndex) {
    await loadChapter(chapterIndex, { scrollTop: false, restoreBlock: idx });
    return;
  }
  highlightBlock(idx);
  scrollToBlock(idx);
  scheduleSaveProgress(idx);
}

async function fetchBlocksPage(offset, limit = CHAPTER_CHUNK) {
  if (chapters.length && currentChapter) {
    const relativeOffset = Math.max(0, offset - currentChapter.start_block);
    return fetchChapterBlocksPage(currentChapterIndex, relativeOffset, limit);
  }
  const page = await api(`/api/readings/${docId}/blocks?offset=${offset}&limit=${limit}`);
  const items = page.items || page;
  items.forEach((b) => {
    currentBlocks[b.order_index] = b;
  });
  loadedBlockCount = Math.max(loadedBlockCount, offset + items.length);
  return page;
}

async function ensureBlocksDataLoaded(upToIndex) {
  await ensureChapterBlocksLoaded(upToIndex);
}

function prefetchBlocks(offset) {
  if (chapters.length && currentChapter) {
    prefetchChapterBlocks(currentChapterIndex, Math.max(0, offset - currentChapter.start_block));
    return;
  }
  fetchBlocksPage(offset, CHAPTER_CHUNK).catch(() => {});
}

async function loadAnnotations() {
  try {
    const [highlights, notes, bookmarks] = await Promise.all([
      api(`/api/readings/${docId}/highlights`),
      api(`/api/readings/${docId}/notes`),
      api(`/api/readings/${docId}/bookmarks`),
    ]);
    currentHighlights = highlights || [];
    currentNotes = notes || [];
    currentBookmarks = bookmarks || [];
    renderNotes();
    renderBookmarks();
    renderToc();
  } catch (_) { /* 标注加载失败不阻塞阅读 */ }
}

async function loadDocument() {
  if (!docId) {
    showToast('缺少文档 ID', 'error');
    return;
  }
  const savedMode = localStorage.getItem('readerDisplayMode');
  if (savedMode) displayMode.value = savedMode;
  applyFontSize();

  try {
    const boot = await api(`/api/readings/${docId}/bootstrap?limit=${CHAPTER_CHUNK}`);
    currentDoc = boot.doc;
    savedWords = new Set(boot.vocab_stats?.words || []);
    updateVocabStatsUI(boot.vocab_stats);
    currentHighlights = boot.highlights || [];
    currentNotes = boot.notes || [];
    currentBookmarks = boot.bookmarks || [];
    totalBlockCount = boot.blocks_total || boot.doc.block_count || 0;
    currentBlocks = new Array(totalBlockCount);
    chapters = boot.chapters || [];
    currentChapterIndex = boot.chapter_index || 0;
    currentChapter = chapters[currentChapterIndex] || null;
    chapterBlockTotal = boot.chapter_block_total || currentChapter?.block_count || boot.blocks?.length || 0;
    chapterLoadedOffset = boot.blocks?.length || 0;
    (boot.blocks || []).forEach((b) => {
      currentBlocks[b.order_index] = b;
    });
    loadedBlockCount = boot.blocks?.length || 0;
    readerTitle.textContent = currentDoc.title;
    document.title = `${currentDoc.title} — VideoEnglish`;
    setupTitleEdit();
    readProgressFill.style.width = `${currentDoc.read_progress || 0}%`;
    updateProgressMeta();
    renderNotes();
    renderBookmarks();
    updateTranslateBanner();
    renderBlocks(currentBlocks, true);
    if (boot.has_more_blocks) prefetchChapterBlocks(currentChapterIndex, chapterLoadedOffset);
    void loadAnnotations();
    if (currentDoc.last_block_index > 0) {
      const resumeChapter = chapterForBlockIndex(currentDoc.last_block_index);
      if (resumeChapter !== currentChapterIndex) {
        await loadChapter(resumeChapter, { scrollTop: false, restoreBlock: currentDoc.last_block_index });
      } else {
        await ensureBlockRendered(currentDoc.last_block_index);
        highlightBlock(currentDoc.last_block_index);
        scrollToBlock(currentDoc.last_block_index);
      }
    }
    startTranslationStream();
    requestChapterTranslation(currentChapterIndex);
    applyTheme();
    maybeShowOnboarding();
  } catch (e) {
    showToast('加载失败: ' + e.message, 'error');
  }
}

async function loadBlocks(fullRender = false) {
  if (loadedBlockCount < totalBlockCount) {
    await fetchBlocksPage(loadedBlockCount, LAZY_CHUNK);
  }
  if (!currentBlocks.filter(Boolean).length) {
    await fetchBlocksPage(0, LAZY_CHUNK);
  }
  if (fullRender || !blockList.querySelector('.reading-block')) {
    renderBlocks(currentBlocks, true);
  } else if (mergeBlocks(currentBlocks.filter(Boolean))) {
    renderBlocks(currentBlocks, false);
  }
}

async function requestChapterTranslation(chapterIndex, { prefetchNext = true } = {}) {
  if (chapterIndex == null || chapterIndex < 0) return;
  try {
    await api(
      `/api/readings/${docId}/translate/chapter/${chapterIndex}?prefetch_next=${prefetchNext ? 'true' : 'false'}`,
      { method: 'POST' },
    );
  } catch (_) { /* 后台会重试 */ }
}

function startTranslationStream(isReconnect = false) {
  if (readEventSource) readEventSource.close();
  clearTimeout(sseRetryTimer);
  const chapterQuery = currentChapterIndex != null ? `?chapter_index=${currentChapterIndex}` : '';
  readEventSource = new EventSource(`/api/readings/${docId}/stream${chapterQuery}`);

  readEventSource.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
    if (currentDoc) {
      Object.assign(currentDoc, data);
      updateTranslateBanner();
    }
  });

  readEventSource.addEventListener('translated', (e) => {
    const data = JSON.parse(e.data);
    if (data.order_index != null) {
      applyTranslationToBlock(data.order_index, data.translation || '', true);
      renderToc();
    }
  });

  readEventSource.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data);
    if (currentDoc) {
      currentDoc.translated_blocks = data.translated_blocks;
      currentDoc.translate_progress = data.translate_progress;
      if (data.status_message) currentDoc.status_message = data.status_message;
      updateTranslateBanner();
    }
  });

  readEventSource.addEventListener('chapter_done', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (currentDoc) {
        Object.assign(currentDoc, data);
      }
      updateTranslateBanner();
      renderToc();
    } catch (_) { /* ignore */ }
  });

  readEventSource.addEventListener('done', (e) => {
    readEventSource?.close();
    readEventSource = null;
    sseRetryCount = 0;
    if (currentDoc) {
      currentDoc.translate_status = 'done';
      try {
        const data = e.data ? JSON.parse(e.data) : {};
        if (data.status_message) currentDoc.status_message = data.status_message;
      } catch (_) { /* ignore */ }
      if (!currentDoc.status_message) currentDoc.status_message = '翻译完成';
    }
    updateTranslateBanner();
    renderToc();
  });

  readEventSource.addEventListener('error', (e) => {
    if (!e.data) return;
    try {
      const data = JSON.parse(e.data);
      if (currentDoc) {
        currentDoc.translate_status = data.translate_status || 'failed';
        currentDoc.status_message = data.message || data.status_message || '翻译失败';
      }
      updateTranslateBanner();
    } catch (_) {}
    readEventSource?.close();
    readEventSource = null;
  });

  readEventSource.onerror = () => {
    if (currentDoc?.translate_status === 'done' || currentDoc?.translate_status === 'failed') {
      readEventSource?.close();
      readEventSource = null;
      return;
    }
    if (currentDoc?.translate_status === 'ready') {
      readEventSource?.close();
      readEventSource = null;
      return;
    }
    readEventSource?.close();
    readEventSource = null;
    scheduleSseReconnect();
  };
}

async function refreshVocabStats() {
  try {
    const stats = await api(`/api/readings/${docId}/vocab-words`);
    savedWords = new Set(stats.words || []);
    updateVocabStatsUI(stats);
    refreshSavedWordHighlights();
  } catch (_) {}
}

function positionHighlightNoteTip(anchorEl) {
  if (!highlightNoteTip || !anchorEl) return;
  const rect = anchorEl.getBoundingClientRect();
  highlightNoteTip.style.top = `${rect.bottom + window.scrollY + 6}px`;
  highlightNoteTip.style.left = `${Math.max(8, rect.left + window.scrollX)}px`;
}

function handleHighlightClick(highlightId, anchorEl) {
  activeHighlightAnchor = anchorEl;
  const note = currentNotes.find((n) => n.highlight_id === highlightId);
  const hl = currentHighlights.find((h) => h.id === highlightId);
  if (note) {
    if (highlightNoteTip) {
      highlightNoteTip.innerHTML = `
        <div class="highlight-note-tip-content">${escapeHtml(note.content)}</div>
        <div class="highlight-note-tip-actions">
          <button class="btn-secondary btn-sm" data-open-notes>全部笔记</button>
          <button class="btn-danger btn-sm" data-del-hl="${highlightId}">删除高亮</button>
        </div>
      `;
      positionHighlightNoteTip(anchorEl);
      highlightNoteTip.classList.remove('hidden');
      highlightNoteTip.querySelector('[data-open-notes]')?.addEventListener('click', () => {
        highlightNoteTip.classList.add('hidden');
        notesPanel.classList.remove('hidden');
        document.body.classList.add('side-open');
      });
      highlightNoteTip.querySelector('[data-del-hl]')?.addEventListener('click', () => {
        deleteHighlight(highlightId);
      });
    }
    return;
  }
  if (highlightNoteTip) {
    highlightNoteTip.innerHTML = `
      <div class="highlight-note-tip-content">「${escapeHtml(hl?.selected_text || '')}」</div>
      <div class="highlight-note-tip-actions">
        <button class="btn-primary btn-sm" data-add-note>添加笔记</button>
        <button class="btn-danger btn-sm" data-del-hl="${highlightId}">删除高亮</button>
      </div>
    `;
    positionHighlightNoteTip(anchorEl);
    highlightNoteTip.classList.remove('hidden');
    highlightNoteTip.querySelector('[data-add-note]')?.addEventListener('click', () => {
      highlightNoteTip.classList.add('hidden');
      pendingHighlightId = highlightId;
      activeBlockIdx = currentBlocks.findIndex((b) => b.id === hl?.block_id);
      notesPanel.classList.remove('hidden');
      document.body.classList.add('side-open');
      newNoteText.value = hl?.selected_text ? `"${hl.selected_text}" — ` : '';
      newNoteText.focus();
    });
    highlightNoteTip.querySelector('[data-del-hl]')?.addEventListener('click', () => {
      deleteHighlight(highlightId);
    });
    return;
  }
  pendingHighlightId = highlightId;
  activeBlockIdx = currentBlocks.findIndex((b) => b.id === hl?.block_id);
  notesPanel.classList.remove('hidden');
  document.body.classList.add('side-open');
  newNoteText.value = hl?.selected_text ? `"${hl.selected_text}" — ` : '';
  newNoteText.focus();
}

async function deleteHighlight(highlightId) {
  try {
    await api(`/api/readings/${docId}/highlights/${highlightId}`, { method: 'DELETE' });
    currentHighlights = currentHighlights.filter((h) => h.id !== highlightId);
    currentNotes.forEach((n) => {
      if (n.highlight_id === highlightId) n.highlight_id = null;
    });
    highlightNoteTip?.classList.add('hidden');
    activeHighlightAnchor = null;
    refreshAllRenderedBlocks();
    renderNotes();
    showToast('高亮已删除', 'success');
  } catch (e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

function renderNotes() {
  if (!currentNotes.length) {
    notesList.innerHTML = '<p class="notes-empty">选中文字高亮后可添加关联笔记，或点击 📝 添加</p>';
    return;
  }
  notesList.innerHTML = currentNotes.map((n) => {
    const block = currentBlocks.find((b) => b.id === n.block_id);
    const hl = n.highlight_id ? currentHighlights.find((h) => h.id === n.highlight_id) : null;
    const hlTag = hl ? `<span class="note-hl-tag">🖍 ${escapeHtml(hl.selected_text.slice(0, 40))}</span>` : '';
    return `
      <div class="note-item" data-note-id="${n.id}">
        <div class="note-meta">${block ? '第 ' + (block.order_index + 1) + ' 段' : '通用'} ${hlTag}</div>
        <div class="note-content">${escapeHtml(n.content)}</div>
        <div class="note-item-actions">
          <button class="btn-secondary btn-sm" data-goto-note="${n.id}">定位</button>
          <button class="btn-secondary btn-sm" data-edit-note="${n.id}">编辑</button>
          <button class="btn-danger btn-sm" data-del-note="${n.id}">删除</button>
        </div>
      </div>`;
  }).join('');
  notesList.querySelectorAll('[data-del-note]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/readings/${docId}/notes/${btn.dataset.delNote}`, { method: 'DELETE' });
      currentNotes = await api(`/api/readings/${docId}/notes`);
      renderNotes();
      refreshAllRenderedBlocks();
    });
  });
  notesList.querySelectorAll('[data-goto-note]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const note = currentNotes.find((n) => n.id === parseInt(btn.dataset.gotoNote, 10));
      goToNote(note);
    });
  });
  notesList.querySelectorAll('[data-edit-note]').forEach((btn) => {
    btn.addEventListener('click', () => startEditNote(parseInt(btn.dataset.editNote, 10)));
  });
}

function startEditNote(noteId) {
  const note = currentNotes.find((n) => n.id === noteId);
  if (!note) return;
  const item = notesList.querySelector(`[data-note-id="${noteId}"]`);
  if (!item) return;
  item.innerHTML = `
    <textarea class="note-edit-input" rows="4"></textarea>
    <div class="note-item-actions">
      <button class="btn-primary btn-sm" data-save-edit="${noteId}">保存</button>
      <button class="btn-secondary btn-sm" data-cancel-edit="${noteId}">取消</button>
    </div>
  `;
  item.querySelector('.note-edit-input').value = note.content;
  item.querySelector('[data-save-edit]').addEventListener('click', async () => {
    const content = item.querySelector('.note-edit-input').value;
    await api(`/api/readings/${docId}/notes/${noteId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    currentNotes = await api(`/api/readings/${docId}/notes`);
    renderNotes();
    showToast('笔记已更新', 'success');
  });
  item.querySelector('[data-cancel-edit]').addEventListener('click', () => renderNotes());
}

async function addNote(content, blockId = null, highlightId = null) {
  if (!content.trim()) return;
  const payload = { content: content.trim(), block_id: blockId };
  if (highlightId) payload.highlight_id = highlightId;
  await api(`/api/readings/${docId}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  currentNotes = await api(`/api/readings/${docId}/notes`);
  pendingHighlightId = null;
  newNoteText.value = '';
  renderNotes();
  refreshAllRenderedBlocks();
  showToast('笔记已保存', 'success');
}

function maybeShowOnboarding() {
  if (localStorage.getItem('reader_onboarding_v1_done')) return;
  onboardingStep = 1;
  onboardingOverlay?.classList.remove('hidden');
  showOnboardingStep(1);
}

function showOnboardingStep(step) {
  onboardingOverlay?.querySelectorAll('.reader-onboarding-step').forEach((el) => {
    el.classList.toggle('hidden', parseInt(el.dataset.step, 10) !== step);
  });
  onboardingOverlay?.classList.toggle('interactive', step === 1 || step === 2);
  if (onboardingNext) {
    onboardingNext.textContent = step >= 3 ? '开始阅读' : '下一步';
  }
}

function finishOnboarding() {
  localStorage.setItem('reader_onboarding_v1_done', '1');
  onboardingOverlay?.classList.add('hidden');
}

function getSelectionOffsetInBlock(blockEl, range) {
  const enEl = blockEl.querySelector('.reading-text-en');
  if (!enEl) return null;
  try {
    const pre = document.createRange();
    pre.selectNodeContents(enEl);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    pre.setEnd(range.endContainer, range.endOffset);
    const end = pre.toString().length;
    const text = range.toString();
    if (!text.trim()) return null;
    return { start, end, text: text };
  } catch {
    return null;
  }
}

function blockElFromNode(node) {
  if (!node) return null;
  const el = node.nodeType === 3 ? node.parentElement : node;
  return el?.closest?.('.reading-block') || null;
}

function getSelectionParts(range) {
  const startBlock = blockElFromNode(range.startContainer);
  const endBlock = blockElFromNode(range.endContainer);
  if (!startBlock || !endBlock) return null;

  const startIdx = parseInt(startBlock.dataset.index, 10);
  const endIdx = parseInt(endBlock.dataset.index, 10);
  if (Number.isNaN(startIdx) || Number.isNaN(endIdx)) return null;

  if (startIdx === endIdx) {
    const offsets = getSelectionOffsetInBlock(startBlock, range);
    if (!offsets || !offsets.text.trim()) return null;
    return [{
      idx: startIdx,
      blockId: currentBlocks[startIdx].id,
      start: offsets.start,
      end: offsets.end,
      text: offsets.text.trim(),
    }];
  }

  if (startIdx > endIdx) return null;
  ensureBlockRendered(endIdx);

  const parts = [];
  for (let i = startIdx; i <= endIdx; i++) {
    const el = blockList.querySelector(`.reading-block[data-index="${i}"]`);
    if (!el) continue;
    const enEl = el.querySelector('.reading-text-en');
    if (!enEl) continue;
    let start = 0;
    let end = enEl.textContent.length;
    if (i === startIdx) {
      try {
        const pre = document.createRange();
        pre.selectNodeContents(enEl);
        pre.setEnd(range.startContainer, range.startOffset);
        start = pre.toString().length;
      } catch {
        continue;
      }
    }
    if (i === endIdx) {
      try {
        const pre = document.createRange();
        pre.selectNodeContents(enEl);
        pre.setEnd(range.endContainer, range.endOffset);
        end = pre.toString().length;
      } catch {
        continue;
      }
    }
    const text = enEl.textContent.slice(start, end);
    if (!text.trim()) continue;
    parts.push({
      idx: i,
      blockId: currentBlocks[i].id,
      start,
      end,
      text: text.trim(),
    });
  }
  return parts.length ? parts : null;
}

function handleTextSelection() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.toString().trim()) {
    selectionToolbar.classList.add('hidden');
    pendingSelection = null;
    return;
  }
  const range = sel.getRangeAt(0);
  const parts = getSelectionParts(range);
  if (!parts) {
    selectionToolbar.classList.add('hidden');
    pendingSelection = null;
    return;
  }
  pendingSelection = {
    parts,
    idx: parts[0].idx,
    blockId: parts[0].blockId,
    start: parts[0].start,
    end: parts[0].end,
    text: parts.map((p) => p.text).join(' '),
  };
  const rect = range.getBoundingClientRect();
  selectionToolbar.style.top = `${rect.top + window.scrollY - 44}px`;
  selectionToolbar.style.left = `${Math.max(8, rect.left + window.scrollX)}px`;
  selectionToolbar.classList.remove('hidden');
}

async function saveHighlight() {
  if (!pendingSelection?.parts?.length) return;
  try {
    for (const part of pendingSelection.parts) {
      const h = await api(`/api/readings/${docId}/highlights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          block_id: part.blockId,
          start_offset: part.start,
          end_offset: part.end,
          selected_text: part.text,
          color: pendingHighlightColor,
        }),
      });
      currentHighlights.push(h);
      refreshBlockAt(part.idx);
    }
    pendingHighlightId = currentHighlights[currentHighlights.length - 1]?.id ?? null;
  } catch (e) {
    showToast('高亮失败: ' + e.message, 'error');
    return;
  }
  selectionToolbar.classList.add('hidden');
  window.getSelection()?.removeAllRanges();
  highlightBlock(pendingSelection.idx);
  showToast(
    pendingSelection.parts.length > 1 ? `已在 ${pendingSelection.parts.length} 段添加高亮` : '已高亮，可继续添加笔记',
    'success',
  );
}

function lookupSelection() {
  if (!pendingSelection) return;
  const word = pendingSelection.text.replace(/[^A-Za-z'-]/g, '').split(/\s+/)[0]?.split("'")[0];
  if (word && word.length > 1) {
    activeBlockIdx = pendingSelection.idx;
    loadWord(word.toLowerCase(), null);
  }
  selectionToolbar.classList.add('hidden');
}

function speakText(text, onEnd) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-US';
  u.rate = 0.9;
  if (onEnd) u.onend = onEnd;
  window.speechSynthesis.speak(u);
  stopTts.classList.remove('hidden');
  ttsToggle.textContent = '🔊 朗读中';
}

function speakBlock(idx) {
  const block = currentBlocks[idx];
  if (!block) return;
  if (!manualSelect) {
    highlightBlock(idx);
  }
  speakText(block.text, () => {
    if (ttsEnabled && idx + 1 < currentBlocks.length) speakBlock(idx + 1);
    else {
      stopTts.classList.add('hidden');
      ttsToggle.textContent = '🔊 开始';
    }
  });
}

function stopSpeaking() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  ttsEnabled = false;
  ttsToggle.textContent = '🔊 开始';
  stopTts.classList.add('hidden');
}

async function loadWord(word, anchorEl) {
  if (!word) return;
  const lookupSeq = ++activeLookupSeq;
  activeWordEl = anchorEl;
  activeWord = word;
  wordPopoverBody.innerHTML = '<div class="word-popover-loading">本地查词中...</div>';
  wordPopover.classList.remove('hidden');
  expandWordBtn.classList.add('hidden');
  saveWordBtn.disabled = true;

  if (anchorEl) {
    wordPopover.style.transform = 'none';
    positionPopover(anchorEl);
  } else {
    wordPopover.style.left = '50%';
    wordPopover.style.top = `${120 + window.scrollY}px`;
    wordPopover.style.transform = 'translateX(-50%)';
  }

  try {
    const fastData = await api(`/api/word-fast/${encodeURIComponent(word)}`);
    if (lookupSeq !== activeLookupSeq) return;
    activeWord = fastData.word;
    activeWordData = fastData;
    renderPopoverCompact(fastData);
    saveWordBtn.disabled = savedWords.has((fastData.word || '').toLowerCase());
  } catch (e) {
    wordPopoverBody.innerHTML = `<div class="word-popover-error">${escapeHtml(e.message)}</div>`;
  }
}

async function saveWord() {
  if (!activeWord || !currentDoc) return;
  const block = currentBlocks[activeBlockIdx] || currentBlocks[0];
  try {
    const saved = await api('/api/vocab/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        word: activeWord,
        source_platform: 'reading',
        source_video_id: `reading-${currentDoc.id}`,
        source_url: `/reader?id=${currentDoc.id}`,
        source_title: currentDoc.title,
        sentence: block?.text || '',
        sentence_translation: block?.translation || '',
      }),
    });
    savedWords.add(saved.word.toLowerCase());
    refreshSavedWordHighlights();
    if (activeWordEl) {
      activeWordEl.classList.add('saved-word', 'save-pulse');
      setTimeout(() => activeWordEl.classList.remove('save-pulse'), 400);
    }
    saveWordBtn.textContent = '★ 已收藏';
    saveWordBtn.disabled = true;
    showToast(`"${saved.word}" 已加入生词本`, 'success');
    await refreshVocabStats();
    if (onboardingStep === 2 && !localStorage.getItem('reader_onboarding_v1_done')) {
      onboardingStep = 3;
      showOnboardingStep(3);
      onboardingOverlay?.classList.remove('hidden');
    }
  } catch (e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

displayMode.addEventListener('change', applyDisplayMode);
readerTheme?.addEventListener('change', () => applyTheme(readerTheme.value, true));
fontSmaller.addEventListener('click', () => { fontSize = Math.max(14, fontSize - 1); applyFontSize(); });
fontBigger.addEventListener('click', () => { fontSize = Math.min(26, fontSize + 1); applyFontSize(); });
ttsToggle.addEventListener('click', () => {
  if (ttsEnabled) { stopSpeaking(); return; }
  ttsEnabled = true;
  speakBlock(activeBlockIdx >= 0 ? activeBlockIdx : (currentDoc?.last_block_index || 0));
});
stopTts.addEventListener('click', stopSpeaking);
saveWordBtn.addEventListener('click', saveWord);
speakWordBtn.addEventListener('click', () => { if (activeWord) speakText(activeWord); });
expandWordBtn.addEventListener('click', () => {
  if (activeWordData) renderPopoverExpanded(activeWordData);
});
wordPopoverBody.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-suggest-word]');
  if (!btn) return;
  e.preventDefault();
  loadWord(btn.dataset.suggestWord, activeWordEl);
});
closePopover.addEventListener('click', hidePopover);
prevChapterBtn?.addEventListener('click', () => {
  if (currentChapterIndex > 0) loadChapter(currentChapterIndex - 1);
});
nextChapterBtn?.addEventListener('click', () => {
  if (currentChapterIndex < chapters.length - 1) loadChapter(currentChapterIndex + 1);
});
document.addEventListener('click', (e) => {
  if (wordPopover.classList.contains('hidden')) return;
  if (wordPopover.contains(e.target)) return;
  hidePopover();
});
document.addEventListener('click', (e) => {
  if (!e.target.closest('.reading-block')) {
    manualSelect = false;
    activeBlockIdx = -1;
    blockList.querySelectorAll('.reading-block').forEach((el) => {
      el.classList.remove('active');
    });
  }
});

function openSidePanel(panel) {
  tocPanel?.classList.add('hidden');
  notesPanel?.classList.add('hidden');
  bookmarksPanel?.classList.add('hidden');
  panel?.classList.remove('hidden');
  document.body.classList.toggle('side-open', !!panel);
}

toggleNotes.addEventListener('click', () => {
  if (notesPanel.classList.contains('hidden')) openSidePanel(notesPanel);
  else { notesPanel.classList.add('hidden'); document.body.classList.remove('side-open'); }
});
closeNotes.addEventListener('click', () => {
  notesPanel.classList.add('hidden');
  document.body.classList.remove('side-open');
});
toggleToc?.addEventListener('click', () => {
  if (tocPanel.classList.contains('hidden')) {
    renderToc();
    openSidePanel(tocPanel);
  } else {
    tocPanel.classList.add('hidden');
    document.body.classList.remove('side-open');
  }
});
closeToc?.addEventListener('click', () => {
  tocPanel.classList.add('hidden');
  document.body.classList.remove('side-open');
});
toggleBookmarks?.addEventListener('click', () => {
  if (bookmarksPanel.classList.contains('hidden')) {
    renderBookmarks();
    openSidePanel(bookmarksPanel);
  } else {
    bookmarksPanel.classList.add('hidden');
    document.body.classList.remove('side-open');
  }
});
closeBookmarks?.addEventListener('click', () => {
  bookmarksPanel.classList.add('hidden');
  document.body.classList.remove('side-open');
});
addBookmarkBtn?.addEventListener('click', addBookmarkAtCurrent);
toggleSearch?.addEventListener('click', openSearchBar);
closeSearch?.addEventListener('click', closeSearchBar);
searchInput?.addEventListener('input', () => {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => runSearch(searchInput.value), 300);
});
searchInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    gotoSearchHit(e.shiftKey ? -1 : 1);
  }
  if (e.key === 'Escape') closeSearchBar();
});
searchPrev?.addEventListener('click', () => gotoSearchHit(-1));
searchNext?.addEventListener('click', () => gotoSearchHit(1));
closeShortcuts?.addEventListener('click', hideShortcuts);
shortcutsOverlay?.addEventListener('click', (e) => {
  if (e.target === shortcutsOverlay) hideShortcuts();
});
progressClickArea?.addEventListener('click', (e) => {
  const bar = progressClickArea.querySelector('.reader-progress-bar');
  if (!bar || !currentDoc?.block_count) return;
  const rect = bar.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  jumpToProgress(pct);
});
toggleSettings.addEventListener('click', () => settingsPanel.classList.toggle('hidden'));
document.getElementById('closeSettings')?.addEventListener('click', () => settingsPanel.classList.add('hidden'));
addNoteBtn.addEventListener('click', () => {
  const block = activeBlockIdx >= 0 ? currentBlocks[activeBlockIdx] : null;
  addNote(newNoteText.value, block?.id || null, pendingHighlightId);
});
highlightBtn.addEventListener('click', saveHighlight);
document.querySelectorAll('.hl-color-btn').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    pendingHighlightColor = btn.dataset.color;
    localStorage.setItem('readerHighlightColor', pendingHighlightColor);
    document.querySelectorAll('.hl-color-btn').forEach((b) => b.classList.toggle('active', b === btn));
  });
});
if (pendingHighlightColor) {
  document.querySelector(`.hl-color-btn[data-color="${pendingHighlightColor}"]`)?.classList.add('active');
}
lookupSelectionBtn.addEventListener('click', lookupSelection);
noteSelectionBtn.addEventListener('click', async () => {
  if (!pendingSelection?.parts?.length) return;
  activeBlockIdx = pendingSelection.idx;
  selectionToolbar.classList.add('hidden');
  window.getSelection()?.removeAllRanges();
  try {
    for (const part of pendingSelection.parts) {
      const h = await api(`/api/readings/${docId}/highlights`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          block_id: part.blockId,
          start_offset: part.start,
          end_offset: part.end,
          selected_text: part.text,
          color: pendingHighlightColor,
        }),
      });
      currentHighlights.push(h);
      refreshBlockAt(part.idx);
    }
    pendingHighlightId = currentHighlights[currentHighlights.length - 1]?.id ?? null;
    highlightBlock(activeBlockIdx);
  } catch (e) {
    showToast('高亮失败: ' + e.message, 'error');
    return;
  }
  notesPanel.classList.remove('hidden');
  document.body.classList.add('side-open');
  newNoteText.value = `"${pendingSelection.text}" — `;
  newNoteText.focus();
});
onboardingNext?.addEventListener('click', () => {
  if (onboardingStep >= 3) {
    finishOnboarding();
    return;
  }
  onboardingStep += 1;
  showOnboardingStep(onboardingStep);
});
onboardingSkip?.addEventListener('click', finishOnboarding);
document.addEventListener('mousedown', (e) => {
  if (highlightNoteTip && !highlightNoteTip.contains(e.target) && !e.target.closest('mark.user-highlight')) {
    highlightNoteTip.classList.add('hidden');
  }
});
document.addEventListener('mouseup', () => setTimeout(handleTextSelection, 10));
document.addEventListener('mousedown', (e) => {
  if (!selectionToolbar.contains(e.target) && !wordPopover.contains(e.target)) {
    selectionToolbar.classList.add('hidden');
  }
});
document.addEventListener('click', (e) => {
  if (e.target.closest('.clickable-word') && onboardingStep === 1 && !localStorage.getItem('reader_onboarding_v1_done')) {
    onboardingStep = 2;
    showOnboardingStep(2);
    onboardingOverlay?.classList.remove('hidden');
  }
});
document.addEventListener('keydown', (e) => {
  const inInput = e.target.matches('textarea, input, select');
  if (e.key === 'Escape') {
    if (!searchBar?.classList.contains('hidden')) { closeSearchBar(); return; }
    if (!shortcutsOverlay?.classList.contains('hidden')) { hideShortcuts(); return; }
    closeAllOverlays();
    return;
  }
  if (inInput && e.key !== 'Escape') return;

  if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
    e.preventDefault();
    showShortcuts();
    return;
  }
  if ((e.key === '/' || ((e.ctrlKey || e.metaKey) && e.key === 'f')) && !inInput) {
    e.preventDefault();
    openSearchBar();
    return;
  }
  if (e.key === 'b' || e.key === 'B') {
    e.preventDefault();
    addBookmarkAtCurrent();
    return;
  }
  if (e.key === 't' || e.key === 'T') {
    e.preventDefault();
    toggleToc?.click();
    return;
  }
  if (e.key === 'n' || e.key === 'N') {
    e.preventDefault();
    toggleNotes?.click();
    return;
  }
  if (e.key === 'ArrowDown' || e.key === 'j') {
    e.preventDefault();
    const next = Math.min(currentBlocks.length - 1, (activeBlockIdx >= 0 ? activeBlockIdx : 0) + 1);
    highlightBlock(next);
    scrollToBlock(next);
  }
  if (e.key === 'ArrowUp' || e.key === 'k') {
    e.preventDefault();
    const prev = Math.max(0, (activeBlockIdx >= 0 ? activeBlockIdx : 0) - 1);
    highlightBlock(prev);
    scrollToBlock(prev);
  }
});
window.addEventListener('load', loadDocument);

function setupTitleEdit() {
  const el = document.getElementById('readerTitle');
  if (!el || el.dataset.editBound) return;
  el.dataset.editBound = '1';
  el.title = '双击可改书名';
  el.addEventListener('dblclick', startEditTitle);
}

async function startEditTitle() {
  if (!currentDoc) return;
  const el = document.getElementById('readerTitle');
  if (!el || el.tagName !== 'H1') return;
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'reader-title-edit';
  input.value = currentDoc.title;
  input.maxLength = 200;
  el.replaceWith(input);
  input.focus();
  input.select();

  const finish = async (save) => {
    let title = currentDoc.title;
    if (save) {
      const newTitle = input.value.trim();
      if (newTitle && newTitle !== currentDoc.title) {
        try {
          currentDoc = await api(`/api/readings/${docId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle }),
          });
          title = currentDoc.title;
          document.title = `${title} — VideoEnglish`;
          showToast('书名已更新', 'success');
        } catch (e) {
          showToast('改名失败: ' + e.message, 'error');
        }
      }
    }
    const h1 = document.createElement('h1');
    h1.id = 'readerTitle';
    h1.className = 'reader-topbar-title';
    h1.textContent = title;
    h1.title = '双击可改书名';
    h1.dataset.editBound = '1';
    h1.addEventListener('dblclick', startEditTitle);
    input.replaceWith(h1);
  };

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    if (e.key === 'Escape') finish(false);
  });
  input.addEventListener('blur', () => finish(true));
}

window.addEventListener('beforeunload', () => {
  stopSpeaking();
  readEventSource?.close();
});
window.addEventListener('scroll', () => {
  if (activeWordEl && !wordPopover.classList.contains('hidden')) positionPopover(activeWordEl);
  if (activeHighlightAnchor && highlightNoteTip && !highlightNoteTip.classList.contains('hidden')) {
    positionHighlightNoteTip(activeHighlightAnchor);
  }
}, { passive: true });
