const wordCache = new Map();
const sentenceCache = new Map();
const translationCallbacks = new Map();

async function fetchWithTimeout(url, options = {}, timeout = 10000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeoutId);
    return resp;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw error;
  }
}

async function translateText(text, source = 'en', target = 'zh') {
  text = text.trim().replace(/\s+/g, ' ');
  if (!text) return '暂无释义';

  if (sentenceCache.has(text)) {
    return sentenceCache.get(text);
  }

  if (typeof AndroidDictionary !== 'undefined') {
    try {
      const result = await new Promise((resolve) => {
        const callbackId = 'tt_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        translationCallbacks.set(callbackId, resolve);
        AndroidDictionary.translateText(text, callbackId);
        
        setTimeout(() => {
          if (translationCallbacks.has(callbackId)) {
            translationCallbacks.delete(callbackId);
            resolve('');
          }
        }, 5000);
      });
      
      if (result && result.trim()) {
        sentenceCache.set(text, result);
        return result;
      }
    } catch (e) {
      console.error('ML Kit error:', e);
    }
  }

  try {
    if (text.length > 450) {
      const sentences = text.split(/(?<=[.!?])\s+/);
      const results = await Promise.all(sentences.map(s => translateText(s)));
      const finalResult = results.join(' ').replace(/\s+/g, ' ');
      sentenceCache.set(text, finalResult);
      return finalResult;
    }

    const resp = await fetchWithTimeout('https://api.mymemory.translated.net/get', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ q: text, langpair: 'en|zh' })
    }, 10000);

    if (resp.ok) {
      const data = await resp.json();
      const result = (data.responseData && data.responseData.translatedText) || '';
      if (result && result !== text && result.toUpperCase() !== text.toUpperCase()) {
        sentenceCache.set(text, result);
        return result;
      }
    }
  } catch (error) {
    console.error('MyMemory error:', error);
  }

  return '暂无释义';
}

async function lookupWord(word) {
  word = word.replace(/[^A-Za-z'-]/g, '').trim().toLowerCase();
  if (!word) {
    return { word: '', pronunciation: '', translation: '暂无释义', example: '' };
  }

  if (wordCache.has(word)) {
    return wordCache.get(word);
  }

  try {
    const dictUrl = `https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word)}`;
    
    const dictPromise = fetch(dictUrl, { method: 'GET' }).then(r => {
      if (!r.ok) throw new Error('Dict API error');
      return r.json();
    }).catch(() => null);

    const [dictData] = await Promise.all([dictPromise]);

    let pronunciation = '';
    let example = '';

    if (dictData && dictData[0]) {
      pronunciation = dictData[0].phonetic || '';
      if (dictData[0].meanings && dictData[0].meanings[0]) {
        const defs = dictData[0].meanings[0].definitions;
        if (defs && defs[0]) {
          example = defs[0].example || '';
        }
      }
    }

    const translation = await translateText(word);

    const result = {
      word,
      pronunciation,
      translation: translation || '暂无释义',
      example
    };

    wordCache.set(word, result);
    return result;
  } catch (error) {
    console.error('Word lookup error:', error);
    
    try {
      const translation = await translateText(word);
      const result = { word, pronunciation: '', translation: translation || '暂无释义', example: '' };
      wordCache.set(word, result);
      return result;
    } catch (e) {
      console.error('Fallback error:', e);
      const result = { word, pronunciation: '', translation: '暂无释义', example: '' };
      wordCache.set(word, result);
      return result;
    }
  }
}

async function translateBatch(texts) {
  const results = [];
  for (const text of texts) {
    results.push(await translateText(text));
    await new Promise(r => setTimeout(r, 200));
  }
  return results;
}
