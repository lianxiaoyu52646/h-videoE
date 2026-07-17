/**
 * 网页阅读 — 手动触发，点击「读」按钮后启动侧边栏
 */
(function () {
  if (document.getElementById('ve-root') || document.getElementById('ve-read-root') || document.getElementById('ve-read-launcher')) return;

  function extractArticleText() {
    const selectors = [
      'article',
      'main',
      '[role="main"]',
      '.post-content',
      '.article-content',
      '.entry-content',
      '.story-body',
      '#content',
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const text = el.innerText.trim();
        if (text.length > 200) return text;
      }
    }
    const paragraphs = [...document.querySelectorAll('p')]
      .map((p) => p.innerText.trim())
      .filter((t) => t.length > 40);
    if (paragraphs.length >= 2) return paragraphs.join('\n\n');
    const body = document.body?.innerText?.trim() || '';
    return body.slice(0, 50000);
  }

  function isEnglishHeavy(text) {
    const letters = (text.match(/[a-zA-Z]/g) || []).length;
    const total = text.replace(/\s/g, '').length;
    return total > 100 && letters / total > 0.5;
  }

  let panel = null;

  function launchReader() {
    if (panel) {
      panel.open = true;
      document.getElementById('ve-read-panel')?.classList.add('ve-open');
      return;
    }
    const text = extractArticleText();
    if (!isEnglishHeavy(text)) {
      alert('未检测到足够的英文正文，无法启动阅读模式。');
      return;
    }
    panel = new WebReadingPanel({
      pageTitle: document.title || location.hostname,
      pageUrl: location.href,
      articleText: text,
    });
    panel.init();
    document.getElementById('ve-read-launcher')?.remove();
  }

  const btn = document.createElement('button');
  btn.id = 've-read-launcher';
  btn.title = 'VideoEnglish 网页阅读';
  btn.textContent = '读';
  btn.addEventListener('click', launchReader);
  document.body.appendChild(btn);
})();
