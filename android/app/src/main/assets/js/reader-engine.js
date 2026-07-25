console.log('[MaBaonanEnglish] reader-engine.js loaded v20260720ap');

const BOOK_FILES = {
    'alice-wonderland': 'books/alice_wonderland.txt',
    'time-machine': 'books/time_machine.txt',
    'pride-prejudice': 'books/pride_prejudice.txt',
    'frankenstein': 'books/frankenstein.txt',
    'great-expectations': 'books/great_expectations.txt',
    'andersen-fairy-tales': 'books/andersen_fairy_tales.txt',
    'andersen-fairy-tales-complete': 'books/andersen_fairy_tales_complete.txt',
    'grimms-fairy-tales': 'books/grimms_fairy_tales.txt'
};

async function loadBookChapters(bookId) {
    console.log('[MaBaonanEnglish] loadBookChapters called with:', bookId);
    const filePath = BOOK_FILES[bookId];
    if (!filePath) {
        console.error('Book not found:', bookId);
        return [];
    }
    
    const content = await BookParser.loadBookFromFile(filePath);
    if (!content) {
        return [];
    }
    
    return BookParser.parseBook(content, bookId);
}

window.loadBookChapters = loadBookChapters;
console.log('[MaBaonanEnglish] loadBookChapters exposed to window');

class BookParser {
    static parseBook(content, bookId) {
        const chapters = [];
        let currentChapter = null;
        
        const chapterPatterns = [
            {
                regex: /^(CHAPTER\s+[IVXLCDM]+\.\s+.*)$/i,
                type: 'alice'
            },
            {
                regex: /^(Chapter\s+\d+)$/i,
                type: 'frankenstein'
            },
            {
                regex: /^(Chapter\s+[IVXLCDM]+)$/i,
                type: 'great_expectations'
            },
            {
                regex: /^(Chapter\s+\d+\.)$/i,
                type: 'pride_prejudice'
            },
            {
                regex: /^\s*([IVXLCDM]+)\s*$/,
                type: 'time_machine_num'
            },
            {
                regex: /^\s*(Introduction|Epilogue)$/,
                type: 'time_machine_title'
            },
            {
                regex: /^(THE\s+[A-Z\s\-’]+)$/,
                type: 'andersen_title'
            },
            {
                regex: /^(PART THE\s+[A-Z\s\-]+)$/,
                type: 'andersen_part'
            },
            {
                regex: /^(TOMMELISE|ELFIN-MOUNT|THE REAL PRINCESS|THE RED SHOES|THE EMPEROR’S NEW CLOTHES|THE SWINEHERD|THE FLYING TRUNK|THE LEAPING MATCH|THE SHEPHERDESS AND THE CHIMNEY-SWEEPER|THE UGLY DUCKLING|THE NAUGHTY BOY)$/,
                type: 'andersen_short'
            },
            {
                regex: /^([A-Z][A-Z\s\-\',]+)$/,
                type: 'grimms_title'
            }
        ];
        
        const lines = content.split('\n');
        let lineIndex = 0;
        let chapterNum = 0;
        let inToc = false;
        let tocEndLine = 0;
        
        for (let i = 0; i < Math.min(lines.length, 100); i++) {
            if (lines[i].includes('CONTENTS') || lines[i].includes('Table of Contents')) {
                inToc = true;
            }
            if (inToc && lines[i].trim() === '' && i > 20) {
                let emptyCount = 0;
                for (let j = i; j < Math.min(i + 10, lines.length); j++) {
                    if (lines[j].trim() === '') emptyCount++;
                }
                if (emptyCount >= 3) {
                    tocEndLine = i;
                    break;
                }
            }
        }
        
        while (lineIndex < lines.length) {
            const line = lines[lineIndex];
            let matched = false;
            
            for (const pattern of chapterPatterns) {
                const match = line.match(pattern.regex);
                if (match) {
                    if (currentChapter) {
                        currentChapter.content = currentChapter.content.trim();
                        if (currentChapter.content.length > 50) {
                            chapters.push(currentChapter);
                        }
                    }
                    
                    let chapterTitle = match[0].trim();
                    
                    if (pattern.type === 'time_machine_num' && lineIndex + 3 < lines.length) {
                        const num = match[1];
                        let title = '';
                        let skip = 1;
                        while (skip <= 5 && lineIndex + skip < lines.length) {
                            const nextLine = lines[lineIndex + skip].trim();
                            if (nextLine && !/^[IVXLCDM]+$/.test(nextLine)) {
                                title = nextLine;
                                break;
                            }
                            skip++;
                        }
                        chapterTitle = num + (title ? ' ' + title : '');
                        lineIndex += skip;
                    } else {
                        lineIndex++;
                    }
                    
                    chapterNum++;
                    currentChapter = {
                        id: `ch${chapterNum}`,
                        title: chapterTitle,
                        content: '',
                        wordCount: 0
                    };
                    matched = true;
                    break;
                }
            }
            
            if (!matched && currentChapter) {
                currentChapter.content += line + '\n';
                lineIndex++;
            } else if (!matched) {
                lineIndex++;
            }
        }
        
        if (currentChapter) {
            currentChapter.content = currentChapter.content.trim();
            if (currentChapter.content.length > 50) {
                chapters.push(currentChapter);
            }
        }
        
        if (chapters.length === 0) {
            chapters.push({
                id: 'ch1',
                title: 'Full Text',
                content: content.replace(/[\x00-\x1F\x7F]/g, ''),
                wordCount: 0
            });
        }
        
        return chapters;
    }
    
    static async loadBookFromFile(filePath) {
        return new Promise((resolve) => {
            if (typeof AndroidDictionary !== 'undefined' && AndroidDictionary.readAssetFile) {
                try {
                    console.log('[MaBaonanEnglish] Loading book via Android API:', filePath);
                    const content = AndroidDictionary.readAssetFile(filePath);
                    if (content) {
                        console.log('[MaBaonanEnglish] Book loaded via Android API, size:', content.length);
                        resolve(content);
                        return;
                    } else {
                        console.error('[MaBaonanEnglish] Android API returned null, falling back to XHR');
                    }
                } catch (e) {
                    console.error('[MaBaonanEnglish] Android API error:', e.message, 'falling back to XHR');
                }
            }
            
            const paths = [
                `file:///android_asset/${filePath}`,
                filePath,
                `./${filePath}`
            ];
            
            let pathIndex = 0;
            
            const tryNextPath = () => {
                if (pathIndex >= paths.length) {
                    console.error('[MaBaonanEnglish] All paths failed');
                    resolve(null);
                    return;
                }
                
                const fullPath = paths[pathIndex];
                pathIndex++;
                
                const xhr = new XMLHttpRequest();
                console.log('[MaBaonanEnglish] Loading book via XHR:', fullPath);
                xhr.open('GET', fullPath, true);
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        console.log('[MaBaonanEnglish] Book loaded via XHR, size:', xhr.responseText.length);
                        resolve(xhr.responseText);
                    } else {
                        console.error(`[MaBaonanEnglish] XHR failed: ${xhr.status}, trying next path`);
                        tryNextPath();
                    }
                };
                xhr.onerror = () => {
                    console.error('[MaBaonanEnglish] XHR network error, trying next path');
                    tryNextPath();
                };
                xhr.timeout = 10000;
                xhr.ontimeout = () => {
                    console.error('[MaBaonanEnglish] XHR timeout, trying next path');
                    tryNextPath();
                };
                xhr.send();
            };
            
            tryNextPath();
        });
    }
    
    static formatContent(content) {
        let html = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        html = html.replace(/\n\n+/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');
        
        return `<p>${html}</p>`;
    }
}

const sentenceTranslationCache = new Map();
const paragraphTranslationCache = new Map();
let translationDB = null;

async function initTranslationDB() {
    if (translationDB) return;
    
    return new Promise((resolve) => {
        const request = indexedDB.open('VideoEnglishTranslation', 1);
        
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('translations')) {
                const store = db.createObjectStore('translations', { keyPath: 'key' });
                store.createIndex('timestamp', 'timestamp');
            }
        };
        
        request.onsuccess = (event) => {
            translationDB = event.target.result;
            resolve();
        };
        
        request.onerror = () => {
            resolve();
        };
    });
}

async function getCachedTranslation(key) {
    if (paragraphTranslationCache.has(key)) {
        return paragraphTranslationCache.get(key);
    }
    
    await initTranslationDB();
    if (!translationDB) return null;
    
    return new Promise((resolve) => {
        const transaction = translationDB.transaction(['translations'], 'readonly');
        const store = transaction.objectStore('translations');
        const request = store.get(key);
        
        request.onsuccess = () => {
            const result = request.result;
            if (result) {
                const translation = result.value;
                paragraphTranslationCache.set(key, translation);
                resolve(translation);
            } else {
                resolve(null);
            }
        };
        
        request.onerror = () => {
            resolve(null);
        };
    });
}

async function setCachedTranslation(key, value) {
    paragraphTranslationCache.set(key, value);
    
    await initTranslationDB();
    if (!translationDB) return;
    
    return new Promise((resolve) => {
        const transaction = translationDB.transaction(['translations'], 'readwrite');
        const store = transaction.objectStore('translations');
        store.put({ key, value, timestamp: Date.now() });
        
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => resolve();
    });
}

function splitIntoSentences(text) {
    const sentences = [];
    const pattern = /([^.!?。！？]+[.!?。！？]+)|([^.!?。！？]+$)/g;
    let match;
    
    while ((match = pattern.exec(text)) !== null) {
        const sentence = match[0].trim();
        if (sentence.length > 0) {
            sentences.push(sentence);
        }
    }
    
    return sentences;
}

function splitIntoParagraphs(content) {
    const paragraphs = content
        .split(/\n\s*\n/)
        .map(p => p.trim())
        .filter(p => p.length > 0);
    
    if (paragraphs.length === 0) {
        const singleParas = content.split('\n').map(p => p.trim()).filter(p => p.length > 0);
        return singleParas.length > 0 ? singleParas : [content];
    }
    
    return paragraphs;
}

const translationCallbacks = new Map();
let mlKitReady = false;

if (typeof AndroidDictionary !== 'undefined' && AndroidDictionary.isTranslatorReady) {
    mlKitReady = AndroidDictionary.isTranslatorReady();
}

window.onTranslateResult = function(callbackId, result) {
    const callback = translationCallbacks.get(callbackId);
    if (callback) {
        callback(result);
        translationCallbacks.delete(callbackId);
    }
};

window.onTranslatorReady = function() {
    mlKitReady = true;
};

function translateViaMLKit(text) {
    return new Promise((resolve) => {
        if (!mlKitReady || typeof AndroidDictionary === 'undefined' || !AndroidDictionary.translateText) {
            resolve(null);
            return;
        }
        const callbackId = 'ml_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        translationCallbacks.set(callbackId, resolve);
        AndroidDictionary.translateText(text, callbackId);
    });
}

class TranslationProgress {
    constructor(total) {
        this.total = total;
        this.completed = 0;
        this.failed = 0;
        this.startTime = Date.now();
        this.paused = false;
    }

    incrementCompleted() { this.completed++; }
    incrementFailed() { this.failed++; }

    getPercent() {
        if (this.total === 0) return 100;
        return Math.min(100, Math.round((this.completed + this.failed) / this.total * 100));
    }

    getEstimatedTime() {
        if (this.completed === 0) return 0;
        const elapsed = (Date.now() - this.startTime) / 1000;
        const avg = elapsed / this.completed;
        const remaining = this.total - this.completed - this.failed;
        return Math.max(0, Math.round(remaining * avg));
    }

    getStatus() {
        if (this.completed + this.failed >= this.total) return 'done';
        if (this.paused) return 'paused';
        return 'translating';
    }
}

class TranslationQueue {
    constructor(maxConcurrent = 3) {
        this.queue = [];
        this.active = 0;
        this.maxConcurrent = maxConcurrent;
        this.cancelled = false;
        this.paused = false;
        this.progress = null;
        this.onProgressUpdate = null;
    }

    setProgressTracker(total) {
        this.progress = new TranslationProgress(total);
    }

    add(text, paragraphId, priority = 1) {
        if (this.cancelled) return;
        this.queue.push({ text, paragraphId, priority });
        this.queue.sort((a, b) => b.priority - a.priority);
    }

    clear() {
        this.queue = [];
        this.cancelled = true;
        this.active = 0;
    }

    pause() {
        this.paused = true;
    }

    resume() {
        this.paused = false;
        this.process();
    }

    cancel() {
        this.clear();
        if (this.progress) this.progress.paused = true;
    }

    async process() {
        if (this.cancelled || this.paused) return;
        while (this.queue.length > 0 && this.active < this.maxConcurrent && !this.cancelled && !this.paused) {
            const task = this.queue.shift();
            this.active++;
            this.executeTask(task);
        }
    }

    async executeTask(task) {
        try {
            const translation = await translateParagraph(task.text);
            if (!this.cancelled) {
                this.updateParagraphUI(task.paragraphId, translation);
                if (this.progress) {
                    this.progress.incrementCompleted();
                    this.notifyProgress();
                }
            }
        } catch (e) {
            if (this.progress) {
                this.progress.incrementFailed();
                this.notifyProgress();
            }
        } finally {
            this.active--;
            if (!this.cancelled && !this.paused && this.queue.length > 0) {
                this.process();
            } else if (this.active === 0 && this.queue.length === 0) {
                this.notifyProgress();
            }
        }
    }

    updateParagraphUI(paragraphId, translation) {
        const zhEl = document.getElementById(`${paragraphId}-zh`);
        if (zhEl) {
            zhEl.classList.remove('loading', 'on-demand');
            zhEl.classList.add('zh-fade-in');
            zhEl.innerHTML = translation || '<span class="no-translation">暂无翻译</span>';
        }
    }

    notifyProgress() {
        if (this.onProgressUpdate && this.progress) {
            this.onProgressUpdate({
                percent: this.progress.getPercent(),
                completed: this.progress.completed,
                failed: this.progress.failed,
                total: this.progress.total,
                estimatedTime: this.progress.getEstimatedTime(),
                status: this.progress.getStatus()
            });
        }
    }
}

let translationQueue = new TranslationQueue(3);

function startChapterTranslation(paragraphs, onProgress) {
    translationQueue.cancel();
    translationQueue = new TranslationQueue(3);
    translationQueue.setProgressTracker(paragraphs.length);
    translationQueue.onProgressUpdate = onProgress;

    for (let i = 0; i < paragraphs.length; i++) {
        const paragraphId = `paragraph-${i}`;
        const priority = i < 3 ? 10 : (i < 6 ? 5 : 1);
        translationQueue.add(paragraphs[i], paragraphId, priority);
    }

    translationQueue.process();
    return translationQueue;
}

class BookTranslationManager {
    constructor(bookId, chapters, onProgress) {
        this.bookId = bookId;
        this.chapters = chapters;
        this.onProgress = onProgress;
        this.activeChapterIndex = 0;
        this.totalParagraphs = 0;
        this.completedParagraphs = 0;
        this.cancelled = false;
        this.paused = false;
        this.startTime = Date.now();
        this.cachedParagraphs = 0;

        for (const chapter of chapters) {
            const paras = splitIntoParagraphs(chapter.content);
            this.totalParagraphs += paras.length;
        }
    }

    async start() {
        await this.translateActiveChapterAndNext();
        this.notifyProgress();
    }

    async translateActiveChapterAndNext() {
        if (this.cancelled) return;

        await this.translateChapter(this.activeChapterIndex);

        if (this.cancelled || this.paused) return;

        const nextIndex = this.activeChapterIndex + 1;
        if (nextIndex < this.chapters.length) {
            await this.translateChapter(nextIndex);
        }
    }

    async translateChapter(chapterIndex) {
        if (chapterIndex < 0 || chapterIndex >= this.chapters.length) return;
        if (this.cancelled) return;

        while (this.paused) {
            await new Promise(r => setTimeout(r, 500));
            if (this.cancelled) return;
        }

        const chapter = this.chapters[chapterIndex];
        const paragraphs = splitIntoParagraphs(chapter.content);

        const cachedCount = await this.countCachedParagraphs(paragraphs);
        if (cachedCount === paragraphs.length) {
            this.completedParagraphs += cachedCount;
            this.notifyProgress();
            return;
        }

        const isActive = chapterIndex === this.activeChapterIndex;

        return new Promise((resolve) => {
            const queue = new TranslationQueue(3);
            const beforeCompleted = this.completedParagraphs;

            queue.setProgressTracker(paragraphs.length);
            queue.onProgressUpdate = (p) => {
                this.completedParagraphs = beforeCompleted + p.completed + p.failed;
                this.notifyProgress({
                    chapterIndex,
                    chapterCompleted: p.completed + p.failed,
                    chapterTotal: p.total,
                    isActive
                });
                if (p.status === 'done') resolve();
            };

            for (let i = 0; i < paragraphs.length; i++) {
                const paragraphId = isActive
                    ? `paragraph-${i}`
                    : `ch${chapterIndex}-paragraph-${i}`;
                const priority = isActive
                    ? (i < 3 ? 10 : (i < 6 ? 5 : 1))
                    : 0;
                queue.add(paragraphs[i], paragraphId, priority);
            }

            queue.process();
            this.currentQueue = queue;
        });
    }

    async countCachedParagraphs(paragraphs) {
        let count = 0;
        for (const p of paragraphs) {
            if (this.cancelled) break;
            const cached = await getCachedTranslation(p.trim());
            if (cached !== null) count++;
        }
        return count;
    }

    notifyProgress(chapterProgress) {
        if (!this.onProgress) return;
        const totalRemaining = this.totalParagraphs - this.completedParagraphs;
        const percent = this.totalParagraphs === 0 ? 100
            : Math.min(100, Math.round(this.completedParagraphs / this.totalParagraphs * 100));
        const elapsed = (Date.now() - this.startTime) / 1000;
        const avg = this.completedParagraphs > 0 ? elapsed / this.completedParagraphs : 0;
        const estimatedTime = Math.max(0, Math.round(totalRemaining * avg));

        this.onProgress({
            bookPercent: percent,
            completedParagraphs: this.completedParagraphs,
            totalParagraphs: this.totalParagraphs,
            currentChapter: this.activeChapterIndex + 1,
            totalChapters: this.chapters.length,
            chapterProgress,
            estimatedTime,
            status: this.cancelled ? 'cancelled'
                : (this.paused ? 'paused'
                : (percent >= 100 ? 'done' : 'translating'))
        });
    }

    async setActiveChapter(chapterIndex) {
        if (this.activeChapterIndex === chapterIndex) return;

        this.activeChapterIndex = chapterIndex;

        if (this.currentQueue) {
            this.currentQueue.cancel();
            this.currentQueue = null;
        }

        this.start();
    }

    pause() {
        this.paused = true;
        if (this.currentQueue) this.currentQueue.pause();
    }

    resume() {
        this.paused = false;
        if (this.currentQueue) this.currentQueue.resume();
    }

    cancel() {
        this.cancelled = true;
        if (this.currentQueue) this.currentQueue.cancel();
    }
}

let bookTranslationManager = null;

function startBookTranslation(bookId, chapters, onProgress) {
    if (bookTranslationManager) {
        bookTranslationManager.cancel();
    }
    bookTranslationManager = new BookTranslationManager(bookId, chapters, onProgress);
    bookTranslationManager.start();
    return bookTranslationManager;
}

function setActiveChapterIndex(index) {
    if (bookTranslationManager) {
        bookTranslationManager.setActiveChapter(index);
    }
}

async function translateParagraph(paragraph) {
    if (!paragraph || paragraph.trim().length === 0) {
        return '';
    }

    const trimmed = paragraph.trim();

    const cached = await getCachedTranslation(trimmed);
    if (cached !== null) {
        return cached;
    }

    let translation = '';

    if (mlKitReady) {
        translation = await translateViaMLKit(trimmed) || '';
    }

    if (!translation) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);

            const resp = await fetch('https://api.mymemory.translated.net/get', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ q: trimmed, langpair: 'en|zh' }).toString(),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (resp.ok) {
                const data = await resp.json();
                if (data.responseData && data.responseData.translatedText) {
                    translation = data.responseData.translatedText;
                    if (translation === trimmed || translation.toUpperCase() === trimmed.toUpperCase()) {
                        translation = '';
                    }
                }
            }
        } catch (error) {
            console.error('Translation fallback error:', error);
        }
    }

    await setCachedTranslation(trimmed, translation);
    return translation;
}

async function translateSentence(sentence) {
    return translateParagraph(sentence);
}

function wrapWordsInParagraph(paragraphHtml) {
    return paragraphHtml.replace(/([a-zA-Z][a-zA-Z'-]*)/g, '<span class="clickable-word">$1</span>');
}

async function renderBilingualChapter(chapterContent, mode = 'bilingual') {
    const paragraphs = splitIntoParagraphs(chapterContent);
    let html = '';
    
    for (let i = 0; i < paragraphs.length; i++) {
        const paragraph = paragraphs[i];
        const paragraphId = `paragraph-${i}`;
        const escapedHtml = escapeHtml(paragraph).replace(/\n/g, '<br>');
        const wrappedHtml = wrapWordsInParagraph(escapedHtml);
        
        let zhHtml = '';
        if (mode === 'bilingual') {
            zhHtml = `<div class="bilingual-zh loading" id="${paragraphId}-zh"><span class="loading-dots">...</span></div>`;
        } else if (mode === 'on-demand') {
            zhHtml = `<div class="bilingual-zh on-demand" id="${paragraphId}-zh" data-loaded="false" onclick="translateOnDemand('${paragraphId}')"><span class="translate-hint">点击翻译</span></div>`;
        }
        
        html += `
            <div class="bilingual-block" id="${paragraphId}" data-paragraph-index="${i}">
                <div class="bilingual-en">${wrappedHtml}</div>
                ${zhHtml}
            </div>
        `;
    }
    
    return { html, paragraphs, count: paragraphs.length };
}

async function preloadTranslations(paragraphs, startIndex = 0, count = 3) {
    const tasks = [];
    for (let i = startIndex; i < Math.min(startIndex + count, paragraphs.length); i++) {
        tasks.push(translateParagraph(paragraphs[i]));
    }
    return Promise.all(tasks);
}

async function lazyTranslateVisibleParagraphs() {
    const paper = document.getElementById('readerPaper');
    if (!paper) return;
    
    const blocks = paper.querySelectorAll('.bilingual-block');
    const visibleIndices = [];
    
    blocks.forEach(block => {
        const rect = block.getBoundingClientRect();
        const isVisible = rect.top < window.innerHeight + 200 && rect.bottom > -200;
        
        if (isVisible) {
            const zhEl = block.querySelector('.bilingual-zh');
            if (zhEl && zhEl.classList.contains('loading')) {
                visibleIndices.push({
                    id: block.id,
                    element: zhEl,
                    enText: block.querySelector('.bilingual-en').textContent
                });
            }
        }
    });
    
    if (visibleIndices.length === 0) return;
    
    const translations = await Promise.all(
        visibleIndices.map(item => translateParagraph(item.enText))
    );
    
    visibleIndices.forEach((item, index) => {
        const translation = translations[index];
        item.element.classList.remove('loading');
        item.element.classList.add('zh-fade-in');
        item.element.innerHTML = translation || '<span class="no-translation">暂无翻译</span>';
    });
}

async function translateOnDemand(paragraphId) {
    const block = document.getElementById(paragraphId);
    if (!block) return;
    
    const zhEl = document.getElementById(`${paragraphId}-zh`);
    if (!zhEl || zhEl.dataset.loaded === 'true') return;
    
    zhEl.innerHTML = '<span class="loading-dots">...</span>';
    zhEl.classList.add('loading');
    
    const enText = block.querySelector('.bilingual-en').textContent;
    const translation = await translateParagraph(enText);
    
    zhEl.classList.remove('loading', 'on-demand');
    zhEl.classList.add('zh-fade-in');
    zhEl.dataset.loaded = 'true';
    zhEl.innerHTML = translation || '<span class="no-translation">暂无翻译</span>';
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
