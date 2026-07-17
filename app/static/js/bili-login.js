// B站扫码登录（视频库页复用）
const biliLoginBtn = document.getElementById('biliLoginBtn');
const biliLoginModal = document.getElementById('biliLoginModal');
const biliQrcodeArea = document.getElementById('biliQrcodeArea');
const biliLoginStatus = document.getElementById('biliLoginStatus');
const biliGenerateBtn = document.getElementById('biliGenerateBtn');
let biliPollTimer = null;

async function api(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) throw new Error(await resp.text());
  return resp.json();
}

async function checkBiliLoginStatus() {
  if (!biliLoginBtn) return;
  try {
    const result = await api('/api/bili/login/status');
    biliLoginBtn.textContent = result.valid ? `✓ ${result.username}` : 'B站登录';
    biliLoginBtn.classList.toggle('logged-in', result.valid);
  } catch (_) {}
}

function closeBiliLoginModal() {
  biliLoginModal?.classList.add('hidden');
  if (biliPollTimer) clearInterval(biliPollTimer);
}
window.closeBiliLoginModal = closeBiliLoginModal;

async function generateBiliQrcode() {
  biliLoginStatus.textContent = '正在生成二维码...';
  biliQrcodeArea.innerHTML = '<div class="bili-qrcode-placeholder">正在生成...</div>';
  if (biliPollTimer) clearInterval(biliPollTimer);
  try {
    const result = await api('/api/bili/login/qrcode');
    if (result.qrcode_image) {
      biliQrcodeArea.innerHTML = `<img src="${result.qrcode_image}" alt="二维码" style="width:220px;height:220px;border-radius:12px;background:#fff;padding:8px;" />`;
      startBiliPolling(result.qrcode_key);
    }
  } catch (e) {
    biliLoginStatus.textContent = '生成失败: ' + e.message;
  }
}

function startBiliPolling(key) {
  biliPollTimer = setInterval(async () => {
    try {
      const r = await api(`/api/bili/login/poll?qrcode_key=${encodeURIComponent(key)}`);
      if (r.status === 'success') {
        clearInterval(biliPollTimer);
        checkBiliLoginStatus();
        setTimeout(() => { closeBiliLoginModal(); location.reload(); }, 1500);
      }
    } catch (_) {}
  }, 2000);
}

biliLoginBtn?.addEventListener('click', () => {
  biliLoginModal.classList.remove('hidden');
  generateBiliQrcode();
});
biliGenerateBtn?.addEventListener('click', generateBiliQrcode);
checkBiliLoginStatus();
