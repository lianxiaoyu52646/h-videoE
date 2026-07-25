const memoryCache = new Map();
let isPreloading = false;

function formatPhonetic(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  
  const usMatch = text.match(/(?:美|US|us)\s*([/\[\(][^/\]\)]+[/\]\)])/);
  const ukMatch = text.match(/(?:英|UK|uk)\s*([/\[\(][^/\]\)]+[/\]\)])/);
  
  if (usMatch && ukMatch) {
    return `<span class="us">US ${usMatch[1]}</span><span class="uk">UK ${ukMatch[1]}</span>`;
  }
  if (usMatch) {
    return `<span class="us">${usMatch[1]}</span>`;
  }
  if (ukMatch) {
    return `<span class="uk">${ukMatch[1]}</span>`;
  }
  
  if (text.startsWith('/') || text.startsWith('[')) return text;
  return `/${text}/`;
}

function isAndroid() {
  return typeof AndroidDictionary !== 'undefined';
}

function getWordDataFromCache(word) {
  if (!word) return null;
  word = word.toLowerCase().trim();
  return memoryCache.get(word) || null;
}

async function preloadChapterWords(chapterContent) {
  if (isPreloading) return;
  isPreloading = true;
  
  try {
    const words = new Set();
    const matches = chapterContent.match(/[a-zA-Z][a-zA-Z'-]*/g);
    if (matches) {
      matches.forEach(w => {
        if (w.length >= 2 && w.length <= 20) {
          words.add(w.toLowerCase());
        }
      });
    }
    
    const uniqueWords = Array.from(words).slice(0, 200);
    const uncachedWords = uniqueWords.filter(w => !memoryCache.has(w));
    
    if (uncachedWords.length === 0) return;
    
    if (isAndroid()) {
      const batchSize = 20;
      for (let i = 0; i < uncachedWords.length; i += batchSize) {
        const batch = uncachedWords.slice(i, i + batchSize);
        await Promise.all(batch.map(async (word) => {
          if (!memoryCache.has(word)) {
            const result = await lookupFromAndroid(word);
            if (result) {
              memoryCache.set(word, result);
            }
          }
        }));
      }
    }
  } catch (e) {
    console.error('Preload error:', e);
  } finally {
    isPreloading = false;
  }
}

function lookupFromAndroid(word) {
  try {
    const result = AndroidDictionary.lookupWord(word);
    if (result) {
      try {
        const data = JSON.parse(result);
        return {
          word: data.word || word,
          pronunciation: data.phonetic || '',
          translation: data.translation || '暂无释义',
          example: '',
          definition: ''
        };
      } catch (e) {
        return null;
      }
    }
  } catch (e) {
    console.error('Android lookup error:', e);
  }
  return null;
}

async function getWordData(word) {
  word = word.toLowerCase().trim();
  if (!word) {
    return { word: '', pronunciation: '', translation: '暂无释义', example: '' };
  }
  
  if (memoryCache.has(word)) {
    return memoryCache.get(word);
  }
  
  let androidResult = null;
  if (isAndroid()) {
    androidResult = lookupFromAndroid(word);
  }
  
  if (androidResult) {
    memoryCache.set(word, androidResult);
    return androidResult;
  }
  
  const dbResult = await lookupFromDB(word);
  if (dbResult) {
    memoryCache.set(word, dbResult);
    return dbResult;
  }
  
  try {
    const translation = await translateText(word);
    const result = {
      word,
      pronunciation: '',
      translation: translation,
      example: ''
    };
    memoryCache.set(word, result);
    if (translation !== '暂无释义') {
      await addWordsToDB([result]);
    }
    return result;
  } catch (e) {
    console.error('Word translation error:', e);
    return { word, pronunciation: '', translation: '暂无释义', example: '' };
  }
}