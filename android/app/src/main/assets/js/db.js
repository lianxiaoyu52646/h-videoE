const DB_NAME = 'VideoEnglishDB';
const DB_VERSION = 3;

let db;

async function openDB() {
  console.log(`[MaBaonanEnglish] [APP-DB] Opening app DB: ${DB_NAME} v${DB_VERSION}`);
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => {
      console.error(`[MaBaonanEnglish] [APP-DB] ERROR: Failed to open DB:`, request.error);
      reject(request.error);
    };
    
    request.onsuccess = () => {
      db = request.result;
      console.log(`[MaBaonanEnglish] [APP-DB] DB opened successfully`);
      resolve(db);
    };
    
    request.onupgradeneeded = (event) => {
      const database = event.target.result;
      console.log(`[MaBaonanEnglish] [APP-DB] DB upgrade needed, creating stores...`);
      
      if (!database.objectStoreNames.contains('wordbooks')) {
        const wordbooksStore = database.createObjectStore('wordbooks', { keyPath: 'id', autoIncrement: true });
        wordbooksStore.createIndex('name', 'name', { unique: false });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: wordbooks`);
      }
      
      if (!database.objectStoreNames.contains('wordbook_entries')) {
        const entriesStore = database.createObjectStore('wordbook_entries', { keyPath: 'id', autoIncrement: true });
        entriesStore.createIndex('wordbook_id', 'wordbook_id', { unique: false });
        entriesStore.createIndex('word', 'word', { unique: false });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: wordbook_entries`);
      }
      
      if (!database.objectStoreNames.contains('reading_progress')) {
        const progressStore = database.createObjectStore('reading_progress', { keyPath: 'doc_id' });
        progressStore.createIndex('doc_id', 'doc_id', { unique: true });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: reading_progress`);
      }
      
      if (!database.objectStoreNames.contains('saved_words')) {
        const savedStore = database.createObjectStore('saved_words', { keyPath: 'word' });
        savedStore.createIndex('word', 'word', { unique: true });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: saved_words`);
      }
      
      if (!database.objectStoreNames.contains('vocab')) {
        const vocabStore = database.createObjectStore('vocab', { keyPath: 'id', autoIncrement: true });
        vocabStore.createIndex('word', 'word', { unique: false });
        vocabStore.createIndex('due', 'due', { unique: false });
        vocabStore.createIndex('source_platform', 'source_platform', { unique: false });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: vocab`);
      }
      
      if (!database.objectStoreNames.contains('reading_documents')) {
        const docsStore = database.createObjectStore('reading_documents', { keyPath: 'id', autoIncrement: true });
        docsStore.createIndex('title', 'title', { unique: false });
        docsStore.createIndex('status', 'status', { unique: false });
        console.log(`[MaBaonanEnglish] [APP-DB] Created store: reading_documents`);
      }
    };
  });
}

async function addWordbook(name, description = '') {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbooks'], 'readwrite');
    const store = transaction.objectStore('wordbooks');
    const request = store.add({ name, description, created_at: new Date().toISOString() });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function removeWordbook(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbooks', 'wordbook_entries'], 'readwrite');
    const entriesStore = transaction.objectStore('wordbook_entries');
    const wordbooksStore = transaction.objectStore('wordbooks');
    
    const entriesIndex = entriesStore.index('wordbook_id');
    entriesIndex.getAll(id).onsuccess = (e) => {
      const entries = e.target.result;
      if (entries.length === 0) {
        wordbooksStore.delete(id);
        return;
      }
      
      let deletedCount = 0;
      entries.forEach(entry => {
        entriesStore.delete(entry.id).onsuccess = () => {
          deletedCount++;
          if (deletedCount === entries.length) {
            wordbooksStore.delete(id);
          }
        };
      });
    };
    
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
}

async function getWordbooks() {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbooks'], 'readonly');
    const store = transaction.objectStore('wordbooks');
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getWordbook(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbooks'], 'readonly');
    const store = transaction.objectStore('wordbooks');
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function addWordbookEntry(wordbookId, word, pronunciation = '', translation = '', example = '') {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbook_entries'], 'readwrite');
    const store = transaction.objectStore('wordbook_entries');
    const request = store.add({
      wordbook_id: wordbookId,
      word,
      pronunciation,
      translation,
      example,
      created_at: new Date().toISOString()
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function removeWordbookEntry(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbook_entries'], 'readwrite');
    const store = transaction.objectStore('wordbook_entries');
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function getWordbookEntries(wordbookId) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbook_entries'], 'readonly');
    const store = transaction.objectStore('wordbook_entries');
    const index = store.index('wordbook_id');
    const request = index.getAll(wordbookId);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveWord(word, data) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['saved_words'], 'readwrite');
    const store = transaction.objectStore('saved_words');
    const request = store.put({
      word: word.toLowerCase(),
      pronunciation: data.pronunciation || '',
      translation: data.translation || '',
      example: data.example || '',
      saved_at: new Date().toISOString()
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function unsaveWord(word) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['saved_words'], 'readwrite');
    const store = transaction.objectStore('saved_words');
    const request = store.delete(word.toLowerCase());
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function isWordSaved(word) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['saved_words'], 'readonly');
    const store = transaction.objectStore('saved_words');
    const request = store.get(word.toLowerCase());
    request.onsuccess = () => resolve(!!request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getSavedWords() {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['saved_words'], 'readonly');
    const store = transaction.objectStore('saved_words');
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveReadingProgress(docId, blockIndex) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_progress'], 'readwrite');
    const store = transaction.objectStore('reading_progress');
    const request = store.put({
      doc_id: docId,
      block_index: blockIndex,
      updated_at: new Date().toISOString()
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getReadingProgress(docId) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_progress'], 'readonly');
    const store = transaction.objectStore('reading_progress');
    const request = store.get(docId);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveVocab(word, data) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['vocab'], 'readwrite');
    const store = transaction.objectStore('vocab');
    const now = new Date();
    const request = store.add({
      word: word.toLowerCase(),
      pronunciation: data.pronunciation || '',
      translation: data.translation || '',
      definition: data.definition || '',
      example: data.example || '',
      source_platform: data.source_platform || 'web',
      source_video_id: data.source_video_id || '',
      source_url: data.source_url || '',
      source_title: data.source_title || '',
      sentence: data.sentence || '',
      sentence_translation: data.sentence_translation || '',
      timestamp: data.timestamp || 0,
      due: now.toISOString(),
      reps: 0,
      created_at: now.toISOString(),
      updated_at: now.toISOString()
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getVocab(filter = {}) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['vocab'], 'readonly');
    const store = transaction.objectStore('vocab');
    const request = store.getAll();
    request.onsuccess = () => {
      let results = request.result;
      if (filter.source_video_id) {
        results = results.filter(v => v.source_video_id === filter.source_video_id);
      }
      results.sort((a, b) => new Date(a.due) - new Date(b.due));
      resolve(results);
    };
    request.onerror = () => reject(request.error);
  });
}

async function getVocabById(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['vocab'], 'readonly');
    const store = transaction.objectStore('vocab');
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function updateVocab(id, data) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['vocab'], 'readwrite');
    const store = transaction.objectStore('vocab');
    const request = store.get(id);
    request.onsuccess = () => {
      const vocab = request.result;
      Object.assign(vocab, data, { updated_at: new Date().toISOString() });
      store.put(vocab).onsuccess = () => resolve();
      store.put(vocab).onerror = () => reject(request.error);
    };
    request.onerror = () => reject(request.error);
  });
}

async function deleteVocab(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['vocab'], 'readwrite');
    const store = transaction.objectStore('vocab');
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

async function addReadingDocument(title, content) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_documents'], 'readwrite');
    const store = transaction.objectStore('reading_documents');
    const blocks = content.split(/\n\n+/).filter(b => b.trim()).map(block => ({
      text_en: block.trim(),
      text_zh: '',
      translated: false
    }));
    const request = store.add({
      title,
      content,
      blocks,
      block_count: blocks.length,
      translated_blocks: 0,
      translate_status: 'ready',
      read_progress: 0,
      last_block_index: 0,
      created_at: new Date().toISOString()
    });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getReadingDocuments() {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_documents'], 'readonly');
    const store = transaction.objectStore('reading_documents');
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getReadingDocument(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_documents'], 'readonly');
    const store = transaction.objectStore('reading_documents');
    const request = store.get(id);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function updateReadingDocument(id, data) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_documents'], 'readwrite');
    const store = transaction.objectStore('reading_documents');
    const request = store.get(id);
    request.onsuccess = () => {
      const doc = request.result;
      Object.assign(doc, data);
      store.put(doc).onsuccess = () => resolve();
      store.put(doc).onerror = () => reject(request.error);
    };
    request.onerror = () => reject(request.error);
  });
}

async function deleteReadingDocument(id) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['reading_documents'], 'readwrite');
    const store = transaction.objectStore('reading_documents');
    const request = store.delete(id);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}