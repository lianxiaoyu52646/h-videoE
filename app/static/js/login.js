const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const statusBox = document.getElementById('authStatus');
const switchBtns = document.querySelectorAll('.auth-switch-btn');
const panels = document.querySelectorAll('.auth-panel');

function showStatus(message, type = '') {
  statusBox.textContent = message || '';
  statusBox.className = `auth-status ${type}`.trim();
}

function setMode(mode) {
  switchBtns.forEach((btn) => btn.classList.toggle('active', btn.dataset.mode === mode));
  panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.mode !== mode));
  showStatus('');
}

function formatDetail(detail) {
  if (!detail) return '请求失败';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('；');
  }
  return String(detail);
}

async function requestJson(url, payload) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    credentials: 'include',
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(formatDetail(data.detail) || '请求失败');
  }
  return data;
}

function nextUrl() {
  const next = new URLSearchParams(window.location.search).get('next');
  if (next && next.startsWith('/') && !next.startsWith('//')) return next;
  return '/app';
}

function setBusy(form, busy) {
  const btn = form.querySelector('.auth-submit');
  if (btn) btn.disabled = !!busy;
}

switchBtns.forEach((btn) => btn.addEventListener('click', () => setMode(btn.dataset.mode)));

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(loginForm);
  const username = String(form.get('username') || '').trim();
  const password = String(form.get('password') || '');
  showStatus('登录中…', 'loading');
  setBusy(loginForm, true);
  try {
    await requestJson('/api/auth/login', { username, password });
    showStatus('登录成功，正在进入…', 'success');
    window.location.href = nextUrl();
  } catch (err) {
    showStatus(err.message, 'error');
    setBusy(loginForm, false);
  }
});

registerForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(registerForm);
  const username = String(form.get('username') || '').trim();
  const password = String(form.get('password') || '');
  showStatus('注册中…', 'loading');
  setBusy(registerForm, true);
  try {
    await requestJson('/api/auth/register', { username, password });
    showStatus('注册成功，正在进入…', 'success');
    window.location.href = nextUrl();
  } catch (err) {
    showStatus(err.message, 'error');
    setBusy(registerForm, false);
  }
});

const mode = new URLSearchParams(window.location.search).get('mode');
setMode(mode === 'register' ? 'register' : 'login');
