(function () {
  const rawFetch = window.fetch.bind(window);
  window.__APP_SHELL__ = window.__APP_SHELL__ || null;

  function isApiRequest(input) {
    const url = typeof input === 'string' ? input : input?.url || '';
    return url.startsWith('/api') || url.startsWith(`${window.location.origin}/api`);
  }

  window.fetch = async function patchedFetch(input, init = {}) {
    const options = { ...init };
    if (isApiRequest(input) && !options.credentials) {
      options.credentials = 'include';
    }
    const resp = await rawFetch(input, options);
    const supportsLogin = window.__APP_SHELL__?.supports_login !== false;
    if (isApiRequest(input) && resp.status === 401 && supportsLogin && window.location.pathname !== '/login') {
      const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
      window.location.href = `/login?next=${next}`;
    }
    return resp;
  };

  async function createExtensionToken() {
    const resp = await rawFetch('/api/auth/tokens', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label: 'extension' }),
    });
    if (!resp.ok) {
      alert('生成扩展令牌失败');
      return;
    }
    const data = await resp.json();
    window.prompt('复制下面的扩展令牌，并粘贴到浏览器扩展设置中：', data.token);
  }

  async function logout() {
    await rawFetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    window.location.href = '/login';
  }

  function applyShellMode(shell) {
    if (!shell) return;
    document.body.dataset.appMode = shell.app_mode;
    document.body.classList.toggle('app-mode-desktop', !!shell.desktop_mode);
  }

  function renderControls(user, shell) {
    const host = document.querySelector('.nav-links') || document.querySelector('.reader-topbar-right');
    if (!host) return;

    const old = document.getElementById('sessionControls');
    if (old) old.remove();

    const wrap = document.createElement('div');
    wrap.id = 'sessionControls';
    wrap.style.display = 'inline-flex';
    wrap.style.gap = '8px';
    wrap.style.alignItems = 'center';

    if (shell?.desktop_mode) {
      return;
    }

    if (!user) {
      const link = document.createElement('a');
      link.href = '/login';
      link.textContent = '登录';
      wrap.appendChild(link);
      host.appendChild(wrap);
      return;
    }

    const text = document.createElement('span');
    text.textContent = user.display_name || user.email;
    text.style.opacity = '0.82';
    text.style.fontSize = '14px';

    const tokenBtn = document.createElement('button');
    tokenBtn.type = 'button';
    tokenBtn.className = 'btn-secondary btn-sm';
    tokenBtn.textContent = '扩展令牌';
    tokenBtn.addEventListener('click', createExtensionToken);

    const logoutBtn = document.createElement('button');
    logoutBtn.type = 'button';
    logoutBtn.className = 'btn-secondary btn-sm';
    logoutBtn.textContent = '退出';
    logoutBtn.addEventListener('click', logout);

    wrap.appendChild(text);
    wrap.appendChild(tokenBtn);
    wrap.appendChild(logoutBtn);
    host.appendChild(wrap);
  }

  async function loadShell() {
    try {
      const resp = await rawFetch('/api/app-shell', { credentials: 'include' });
      if (!resp.ok) return null;
      const shell = await resp.json();
      window.__APP_SHELL__ = shell;
      applyShellMode(shell);
      return shell;
    } catch (_) {
      return null;
    }
  }

  async function bootstrap() {
    const shell = await loadShell();
    if (window.location.pathname === '/login' && shell?.supports_login === false) {
      window.location.href = '/';
      return;
    }
    if (window.location.pathname === '/login') return;
    try {
      const resp = await rawFetch('/api/auth/me', { credentials: 'include' });
      if (!resp.ok) {
        renderControls(null, shell);
        return;
      }
      const user = await resp.json();
      renderControls(user, shell);
    } catch (_) {
      renderControls(null, shell);
    }
  }

  window.addEventListener('DOMContentLoaded', bootstrap);
})();
