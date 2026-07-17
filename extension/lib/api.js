const VideoEnglishAPI = {
  async getBase() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(['apiBase'], (data) => {
        resolve(data.apiBase || 'http://127.0.0.1:8000');
      });
    });
  },

  async getToken() {
    return new Promise((resolve) => {
      chrome.storage.sync.get(['apiToken'], (data) => {
        resolve(data.apiToken || '');
      });
    });
  },

  async request(path, options = {}) {
    const base = await this.getBase();
    const token = await this.getToken();
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const resp = await fetch(`${base}${path}`, {
      ...options,
      headers,
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || resp.statusText);
    }
    return resp.json();
  },

  lookupWord(word) {
    return this.request(`/api/word/${encodeURIComponent(word)}`);
  },

  saveWord(payload) {
    return this.request('/api/vocab/save', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  translateBatch(texts) {
    return this.request('/api/translate/batch', {
      method: 'POST',
      body: JSON.stringify({ texts, source: 'en', target: 'zh-CN' }),
    });
  },

  listSavedWords(sourceId) {
    const q = sourceId ? `?source_video_id=${encodeURIComponent(sourceId)}` : '';
    return this.request(`/api/vocab${q}`);
  },

  createReading({ title, content, source_type = 'web', source_url = '' }) {
    return this.request('/api/readings', {
      method: 'POST',
      body: JSON.stringify({ title, content, source_type, source_url }),
    });
  },

  getReading(docId) {
    return this.request(`/api/readings/${docId}`);
  },

  getReadingBlocks(docId) {
    return this.request(`/api/readings/${docId}/blocks`);
  },

  migrateVocab(docId, { from_source_id, source_platform, source_url, source_title }) {
    return this.request(`/api/readings/${docId}/migrate-vocab`, {
      method: 'POST',
      body: JSON.stringify({ from_source_id, source_platform, source_url, source_title }),
    });
  },
};
