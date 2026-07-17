const apiInput = document.getElementById('apiBase');
const tokenInput = document.getElementById('apiToken');
const saveBtn = document.getElementById('saveBtn');
const ok = document.getElementById('ok');

chrome.storage.sync.get(['apiBase', 'apiToken'], (data) => {
  apiInput.value = data.apiBase || 'http://127.0.0.1:8000';
  tokenInput.value = data.apiToken || '';
});

saveBtn.addEventListener('click', () => {
  chrome.storage.sync.set({
    apiBase: apiInput.value.trim(),
    apiToken: tokenInput.value.trim(),
  }, () => {
    ok.style.display = 'block';
    setTimeout(() => { ok.style.display = 'none'; }, 2000);
  });
});
