const DB_NAME = 'VideoEnglishDB';
const DB_VERSION = 1;

let db;

async function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => reject(request.error);
    
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };
    
    request.onupgradeneeded = (event) => {
      const database = event.target.result;
      
      if (!database.objectStoreNames.contains('wordbooks')) {
        const wordbooksStore = database.createObjectStore('wordbooks', { keyPath: 'id', autoIncrement: true });
        wordbooksStore.createIndex('name', 'name', { unique: false });
      }
      
      if (!database.objectStoreNames.contains('wordbook_entries')) {
        const entriesStore = database.createObjectStore('wordbook_entries', { keyPath: 'id', autoIncrement: true });
        entriesStore.createIndex('wordbook_id', 'wordbook_id', { unique: false });
        entriesStore.createIndex('word', 'word', { unique: false });
      }
      
      if (!database.objectStoreNames.contains('reading_progress')) {
        const progressStore = database.createObjectStore('reading_progress', { keyPath: 'doc_id' });
        progressStore.createIndex('doc_id', 'doc_id', { unique: true });
      }
      
      if (!database.objectStoreNames.contains('saved_words')) {
        const savedStore = database.createObjectStore('saved_words', { keyPath: 'word' });
        savedStore.createIndex('word', 'word', { unique: true });
      }
    };
  });
}

async function addWordbook(name) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbooks'], 'readwrite');
    const store = transaction.objectStore('wordbooks');
    const request = store.add({ name, created_at: new Date().toISOString() });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
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

async function addWordbookEntry(wordbookId, entry) {
  await openDB();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['wordbook_entries'], 'readwrite');
    const store = transaction.objectStore('wordbook_entries');
    const request = store.add({
      wordbook_id: wordbookId,
      word: entry.word,
      pronunciation: entry.pronunciation || '',
      translation: entry.translation || '',
      example: entry.example || '',
      created_at: new Date().toISOString()
    });
    request.onsuccess = () => resolve(request.result);
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