const DICT_DB_NAME = 'VideoEnglishDictDB';
const DICT_DB_VERSION = 1;
const DICT_STORE_NAME = 'dictionary';

let dictDB;

async function openDictDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DICT_DB_NAME, DICT_DB_VERSION);
    
    request.onerror = () => reject(request.error);
    
    request.onsuccess = () => {
      dictDB = request.result;
      resolve(dictDB);
    };
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(DICT_STORE_NAME)) {
        const store = db.createObjectStore(DICT_STORE_NAME, { keyPath: 'word' });
        store.createIndex('word_lower', 'word_lower', { unique: true });
      }
    };
  });
}

async function addWordsToDB(words) {
  await openDictDB();
  return new Promise((resolve, reject) => {
    const transaction = dictDB.transaction([DICT_STORE_NAME], 'readwrite');
    const store = transaction.objectStore(DICT_STORE_NAME);
    
    let count = 0;
    for (const word of words) {
      const request = store.put({
        word: word.word,
        word_lower: word.word.toLowerCase(),
        pronunciation: word.pronunciation || '',
        translation: word.translation || '',
        example: word.example || '',
        definition: word.definition || ''
      });
      request.onsuccess = () => count++;
    }
    
    transaction.oncomplete = () => resolve(count);
    transaction.onerror = () => reject(transaction.error);
  });
}

async function lookupFromDB(word) {
  await openDictDB();
  return new Promise((resolve, reject) => {
    const transaction = dictDB.transaction([DICT_STORE_NAME], 'readonly');
    const store = transaction.objectStore(DICT_STORE_NAME);
    const index = store.index('word_lower');
    const request = index.get(word.toLowerCase());
    
    request.onsuccess = () => {
      if (request.result) {
        resolve({
          word: request.result.word,
          pronunciation: request.result.pronunciation,
          translation: request.result.translation,
          example: request.result.example,
          definition: request.result.definition
        });
      } else {
        resolve(null);
      }
    };
    
    request.onerror = () => reject(request.error);
  });
}

async function getWordCountFromDB() {
  await openDictDB();
  return new Promise((resolve, reject) => {
    const transaction = dictDB.transaction([DICT_STORE_NAME], 'readonly');
    const store = transaction.objectStore(DICT_STORE_NAME);
    const request = store.count();
    
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function initDictionaryDB() {
  await openDictDB();
  const count = await getWordCountFromDB();
  
  if (count === 0) {
    console.log('Initializing dictionary DB...');
    const words = await loadDictionaryJSON();
    const added = await addWordsToDB(words);
    console.log('Dictionary DB initialized:', added, 'words');
  }
  
  return count;
}

async function loadDictionaryJSON() {
  try {
    const resp = await fetch('assets/core_en.json');
    const data = await resp.json();
    if (data.entries && Array.isArray(data.entries)) {
      return data.entries;
    }
    return [];
  } catch (error) {
    console.error('Failed to load dictionary JSON:', error);
    return [];
  }
}