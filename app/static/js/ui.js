// ── 全站共享 UI 组件层：Toast 提示 + 弹窗（确认/输入） ──
// 用现代化的浮层组件替换原生 alert/confirm/prompt，统一交互与视觉。
(function () {
  if (window.UI) return;

  let toastHost = null;
  function ensureToastHost() {
    if (toastHost && document.body.contains(toastHost)) return toastHost;
    toastHost = document.createElement('div');
    toastHost.className = 'ui-toast-host';
    document.body.appendChild(toastHost);
    return toastHost;
  }

  function toast(message, type = 'info', timeout = 2600) {
    const host = ensureToastHost();
    const el = document.createElement('div');
    el.className = `ui-toast ui-toast-${type}`;
    const icon = { success: '✓', error: '✕', warning: '!', info: 'ℹ' }[type] || 'ℹ';
    el.innerHTML = `<span class="ui-toast-icon">${icon}</span><span class="ui-toast-msg"></span>`;
    el.querySelector('.ui-toast-msg').textContent = message;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    const remove = () => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 220);
    };
    if (timeout > 0) setTimeout(remove, timeout);
    el.addEventListener('click', remove);
    return remove;
  }

  function buildModal({ title, body, actions }) {
    const overlay = document.createElement('div');
    overlay.className = 'ui-modal-overlay';
    const modal = document.createElement('div');
    modal.className = 'ui-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    const head = document.createElement('div');
    head.className = 'ui-modal-head';
    head.textContent = title || '';

    const content = document.createElement('div');
    content.className = 'ui-modal-body';
    if (typeof body === 'string') content.innerHTML = body;
    else if (body instanceof Node) content.appendChild(body);

    const footer = document.createElement('div');
    footer.className = 'ui-modal-footer';

    modal.appendChild(head);
    if (content.childNodes.length || content.innerHTML) modal.appendChild(content);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    const close = (result) => {
      overlay.classList.remove('show');
      setTimeout(() => overlay.remove(), 200);
      document.removeEventListener('keydown', onKey);
      if (overlay._resolve) overlay._resolve(result);
    };
    overlay._close = close;

    (actions || []).forEach((action) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = action.className || 'btn-secondary';
      btn.textContent = action.label;
      btn.addEventListener('click', () => {
        if (action.onClick) {
          const maybe = action.onClick();
          if (maybe === false) return;
        }
        close(action.value);
      });
      footer.appendChild(btn);
    });

    function onKey(e) {
      if (e.key === 'Escape') close(overlay._cancelValue);
    }
    document.addEventListener('keydown', onKey);
    overlay.addEventListener('mousedown', (e) => {
      if (e.target === overlay) close(overlay._cancelValue);
    });

    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('show'));
    return { overlay, modal, content, footer, close };
  }

  function confirmDialog({ title = '确认操作', message = '', confirmText = '确定', cancelText = '取消', danger = false } = {}) {
    return new Promise((resolve) => {
      const { overlay } = buildModal({
        title,
        body: `<p class="ui-modal-text"></p>`,
        actions: [
          { label: cancelText, className: 'btn-secondary', value: false },
          { label: confirmText, className: danger ? 'btn-danger' : 'btn-primary', value: true },
        ],
      });
      overlay._resolve = resolve;
      overlay._cancelValue = false;
      overlay.querySelector('.ui-modal-text').textContent = message;
    });
  }

  function promptDialog({ title = '请输入', message = '', value = '', placeholder = '', confirmText = '确定', cancelText = '取消' } = {}) {
    return new Promise((resolve) => {
      const wrapper = document.createElement('div');
      if (message) {
        const p = document.createElement('p');
        p.className = 'ui-modal-text';
        p.textContent = message;
        wrapper.appendChild(p);
      }
      const input = document.createElement('input');
      input.className = 'ui-modal-input';
      input.value = value;
      input.placeholder = placeholder;
      wrapper.appendChild(input);

      const { overlay } = buildModal({
        title,
        body: wrapper,
        actions: [
          { label: cancelText, className: 'btn-secondary', value: null },
          {
            label: confirmText,
            className: 'btn-primary',
            get value() {
              return input.value;
            },
          },
        ],
      });
      overlay._resolve = (result) => resolve(result == null ? null : result);
      overlay._cancelValue = null;
      setTimeout(() => input.focus(), 60);
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') overlay._close(input.value);
      });
    });
  }

  window.UI = { toast, confirmDialog, promptDialog, buildModal };
})();
