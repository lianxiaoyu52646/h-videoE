const memoryCache = new Map();

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

async function getWordData(word) {
  word = word.toLowerCase().trim();
  if (!word) {
    return { word: '', pronunciation: '', translation: '暂无释义', example: '' };
  }
  
  if (memoryCache.has(word)) {
    return memoryCache.get(word);
  }
  
  const dbResult = await lookupFromDB(word);
  if (dbResult) {
    memoryCache.set(word, dbResult);
    return dbResult;
  }
  
  const result = await lookupWord(word);
  memoryCache.set(word, result);
  
  if (result.translation && result.translation !== '暂无释义') {
    await addWordsToDB([result]);
  }
  
  return result;
}