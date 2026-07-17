const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const statusBox = document.getElementById('authStatus');
const switchBtns = document.querySelectorAll('.auth-switch-btn');
const panels = document.querySelectorAll('.auth-panel');

function showStatus(message, type = '') {
  statusBox.textContent = message;
  statusBox.className = `status-msg ${type}`.trim();
}

function setMode(mode) {
  switchBtns.forEach((btn) => btn.classList.toggle('active', btn.dataset.mode === mode));
  panels.forEach((panel) => panel.classList.toggle('hidden', panel.dataset.mode !== mode));
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
    throw new Error(data.detail || '请求失败');
  }
  return data;
}

function nextUrl() {
  const next = new URLSearchParams(window.location.search).get('next');
  return next || '/';
}

switchBtns.forEach((btn) => btn.addEventListener('click', () => setMode(btn.dataset.mode)));

loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(loginForm);
  showStatus('登录中...', 'loading');
  try {
    await requestJson('/api/auth/login', {
      email: form.get('email'),
      password: form.get('password'),
    });
    showStatus('登录成功，正在跳转...', 'success');
    window.location.href = nextUrl();
  } catch (err) {
    showStatus(err.message, 'error');
  }
});

registerForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = new FormData(registerForm);
  showStatus('注册中...', 'loading');
  try {
    await requestJson('/api/auth/register', {
      email: form.get('email'),
      password: form.get('password'),
      display_name: form.get('display_name'),
    });
    showStatus('注册成功，正在跳转...', 'success');
    window.location.href = nextUrl();
  } catch (err) {
    showStatus(err.message, 'error');
  }
});

setMode('login');
