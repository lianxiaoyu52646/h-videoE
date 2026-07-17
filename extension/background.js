chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get(['apiBase'], (data) => {
    if (!data.apiBase) {
      chrome.storage.sync.set({ apiBase: 'http://127.0.0.1:8000' });
    }
  });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'getApiBase') {
    chrome.storage.sync.get(['apiBase'], (data) => {
      sendResponse({ apiBase: data.apiBase || 'http://127.0.0.1:8000' });
    });
    return true;
  }
});
