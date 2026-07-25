const wordCache = new Map();
const sentenceCache = new Map();

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

  try {
    const resp = await fetchWithTimeout('https://api.mymemory.translated.net/get', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ q: text, langpair: 'en|zh' })
    }, 10000);

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    
    const data = await resp.json();
    const result = (data.responseData && data.responseData.translatedText) || '暂无释义';
    
    sentenceCache.set(text, result);
    return result;
  } catch (error) {
    console.error('Translation error:', error);
    sentenceCache.set(text, '暂无释义');
    return '暂无释义';
  }
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
    const transUrl = 'https://api.mymemory.translated.net/get';
    
    const dictPromise = fetch(dictUrl, { method: 'GET' }).then(r => {
      if (!r.ok) throw new Error('Dict API error');
      return r.json();
    }).catch(() => null);
    
    const transPromise = fetch(transUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ q: word, langpair: 'en|zh' })
    }).then(r => {
      if (!r.ok) throw new Error('Trans API error');
      return r.json();
    }).catch(() => null);

    const [dictData, transData] = await Promise.all([dictPromise, transPromise]);

    let pronunciation = '';
    let example = '';
    let definition = '';

    if (dictData && dictData[0]) {
      pronunciation = dictData[0].phonetic || '';
      if (dictData[0].meanings && dictData[0].meanings[0]) {
        const defs = dictData[0].meanings[0].definitions;
        if (defs && defs[0]) {
          example = defs[0].example || '';
          definition = defs[0].definition || '';
        }
      }
    }

    let translation = '';
    if (transData && transData.responseData && transData.responseData.translatedText) {
      translation = transData.responseData.translatedText;
    }

    const result = {
      word,
      pronunciation,
      translation: translation || definition || '暂无释义',
      example
    };

    wordCache.set(word, result);
    return result;
  } catch (error) {
    console.error('Word lookup error:', error);
    
    try {
      const resp = await fetch('https://api.mymemory.translated.net/get', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ q: word, langpair: 'en|zh' })
      });

      let translation = '暂无释义';
      if (resp.ok) {
        const data = await resp.json();
        if (data.responseData && data.responseData.translatedText) {
          translation = data.responseData.translatedText;
        }
      }

      const result = { word, pronunciation: '', translation, example: '' };
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