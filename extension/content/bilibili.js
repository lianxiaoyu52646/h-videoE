(function () {
  'use strict';

  function getBvid() {
    const m = location.pathname.match(/\/video\/(BV[\w]+)/i);
    return m ? m.group(1) : '';
  }

  function getVideoTitle() {
    return document.querySelector('h1, .video-title')?.textContent?.trim()
      || document.title.replace(/_哔哩哔哩.*/, '');
  }

  function getVideoEl() {
    return document.querySelector('video');
  }

  async function fetchBilibiliCaptionsViaBackend() {
    const url = location.href;
    const base = await VideoEnglishAPI.getBase();
    const resp = await fetch(`${base}/api/videos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const video = await resp.json();

    // 轮询字幕直到就绪（最多 90 秒）
    for (let i = 0; i < 45; i++) {
      const subsResp = await fetch(`${base}/api/videos/${video.id}/subtitles`);
      if (subsResp.ok) {
        const subs = await subsResp.json();
        if (subs.length) {
          return subs.map(s => ({
            start: s.start,
            end: s.end,
            text: s.text,
            translation: s.translation || '',
          }));
        }
      }
      await new Promise(r => setTimeout(r, 2000));
    }
    throw new Error('字幕加载超时。请先在 Web 端 B站登录，或该视频无字幕。');
  }

  async function boot() {
    const bvid = getBvid();
    if (!bvid) return;

    await new Promise((r) => setTimeout(r, 2000));

    const panel = new LearningPanel({
      platform: 'bilibili',
      videoId: bvid,
      videoTitle: getVideoTitle(),
      videoUrl: location.href,
      getVideoEl,
      loadCaptions: fetchBilibiliCaptionsViaBackend,
    });
    await panel.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
