const DICT_DB_NAME = 'VideoEnglishDictDB';
const DICT_DB_VERSION = 1;
const DICT_STORE_NAME = 'dictionary';

let dictDB;

async function openDictDB() {
  console.log(`[MaBaonanEnglish] [DICT-DB] Opening dictionary DB: ${DICT_DB_NAME} v${DICT_DB_VERSION}`);
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DICT_DB_NAME, DICT_DB_VERSION);
    
    request.onerror = () => {
      console.error(`[MaBaonanEnglish] [DICT-DB] ERROR: Failed to open DB:`, request.error);
      reject(request.error);
    };
    
    request.onsuccess = () => {
      dictDB = request.result;
      console.log(`[MaBaonanEnglish] [DICT-DB] DB opened successfully`);
      resolve(dictDB);
    };
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      console.log(`[MaBaonanEnglish] [DICT-DB] DB upgrade needed, creating stores...`);
      if (!db.objectStoreNames.contains(DICT_STORE_NAME)) {
        const store = db.createObjectStore(DICT_STORE_NAME, { keyPath: 'word' });
        store.createIndex('word_lower', 'word_lower', { unique: true });
        console.log(`[MaBaonanEnglish] [DICT-DB] Created store: ${DICT_STORE_NAME}`);
      }
    };
  });
}

async function addWordsToDB(words) {
  console.log(`[MaBaonanEnglish] [DICT-DB] Adding ${words.length} words to DB`);
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
    
    transaction.oncomplete = () => {
      console.log(`[MaBaonanEnglish] [DICT-DB] Added ${count} words successfully`);
      resolve(count);
    };
    transaction.onerror = () => {
      console.error(`[MaBaonanEnglish] [DICT-DB] ERROR: Failed to add words:`, transaction.error);
      reject(transaction.error);
    };
  });
}

async function lookupFromDB(word) {
  console.log(`[MaBaonanEnglish] [DICT-DB] Looking up word: ${word}`);
  await openDictDB();
  return new Promise((resolve, reject) => {
    const transaction = dictDB.transaction([DICT_STORE_NAME], 'readonly');
    const store = transaction.objectStore(DICT_STORE_NAME);
    const index = store.index('word_lower');
    const request = index.get(word.toLowerCase());
    
    request.onsuccess = () => {
      if (request.result) {
        console.log(`[MaBaonanEnglish] [DICT-DB] Found word: ${word}`);
        resolve({
          word: request.result.word,
          pronunciation: request.result.pronunciation,
          translation: request.result.translation,
          example: request.result.example,
          definition: request.result.definition
        });
      } else {
        console.log(`[MaBaonanEnglish] [DICT-DB] Word not found: ${word}`);
        resolve(null);
      }
    };
    
    request.onerror = () => {
      console.error(`[MaBaonanEnglish] [DICT-DB] ERROR: Lookup failed:`, request.error);
      reject(request.error);
    };
  });
}

async function getWordCountFromDB() {
  await openDictDB();
  return new Promise((resolve, reject) => {
    const transaction = dictDB.transaction([DICT_STORE_NAME], 'readonly');
    const store = transaction.objectStore(DICT_STORE_NAME);
    const request = store.count();
    
    request.onsuccess = () => {
      console.log(`[MaBaonanEnglish] [DICT-DB] Word count: ${request.result}`);
      resolve(request.result);
    };
    request.onerror = () => {
      console.error(`[MaBaonanEnglish] [DICT-DB] ERROR: Count failed:`, request.error);
      reject(request.error);
    };
  });
}

async function initDictionaryDB() {
  console.log(`[MaBaonanEnglish] [DICT-DB] Initializing dictionary DB...`);
  await openDictDB();
  const count = await getWordCountFromDB();
  
  if (count === 0) {
    console.log(`[MaBaonanEnglish] [DICT-DB] DB is empty, loading JSON...`);
    const words = await loadDictionaryJSON();
    console.log(`[MaBaonanEnglish] [DICT-DB] Loaded ${words.length} words from JSON`);
    const added = await addWordsToDB(words);
    console.log(`[MaBaonanEnglish] [DICT-DB] Dictionary DB initialized with ${added} words`);
  } else {
    console.log(`[MaBaonanEnglish] [DICT-DB] DB already has ${count} words, skipping initialization`);
  }
  
  return count;
}

async function loadDictionaryJSON() {
  console.log(`[MaBaonanEnglish] [DICT-DB] Loading dictionary JSON...`);
  try {
    const paths = ['assets/core_en.json', '../assets/core_en.json', 'core_en.json'];
    for (const path of paths) {
      try {
        console.log(`[MaBaonanEnglish] [DICT-DB] Trying path: ${path}`);
        const resp = await fetch(path);
        if (resp.ok) {
          console.log(`[MaBaonanEnglish] [DICT-DB] Fetch successful for: ${path}`);
          const data = await resp.json();
          if (data.entries && Array.isArray(data.entries)) {
            console.log(`[MaBaonanEnglish] [DICT-DB] Found ${data.entries.length} entries`);
            return data.entries;
          }
        } else {
          console.log(`[MaBaonanEnglish] [DICT-DB] Fetch failed for ${path}, status: ${resp.status}`);
        }
      } catch (e) {
        console.log(`[MaBaonanEnglish] [DICT-DB] Fetch error for ${path}:`, e);
      }
    }
    console.log(`[MaBaonanEnglish] [DICT-DB] All paths failed, returning empty array`);
    return [];
  } catch (error) {
    console.error(`[MaBaonanEnglish] [DICT-DB] ERROR: Failed to load dictionary JSON:`, error);
    return [];
  }
}