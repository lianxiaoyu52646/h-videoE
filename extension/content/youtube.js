(function () {
  'use strict';

  function getVideoId() {
    return new URLSearchParams(location.search).get('v') || '';
  }

  function getVideoTitle() {
    return document.querySelector('h1.ytd-watch-metadata yt-formatted-string, h1.title')?.textContent?.trim()
      || document.title.replace(' - YouTube', '');
  }

  function getVideoEl() {
    return document.querySelector('video.html5-main-video, video');
  }

  function getCaptionTracks() {
    const pr = window.ytInitialPlayerResponse;
    if (!pr) return [];
    return pr.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  }

  function parseJson3(data) {
    const segments = [];
    for (const event of data.events || []) {
      if (!event.segs) continue;
      const text = event.segs.map((s) => s.utf8 || '').join('').replace(/\n/g, ' ').trim();
      if (!text) continue;
      const start = (event.tStartMs || 0) / 1000;
      const duration = (event.dDurationMs || 2000) / 1000;
      segments.push({ start, end: start + Math.max(duration, 0.5), text, translation: '' });
    }
    return segments;
  }

  async function fetchYouTubeCaptions() {
    const tracks = getCaptionTracks();
    if (!tracks.length) return [];

    let track = tracks.find((t) => /^en/i.test(t.languageCode))
      || tracks.find((t) => /english/i.test(t.name?.simpleText || ''))
      || tracks[0];

    let url = track.baseUrl;
    if (!url.includes('fmt=')) url += (url.includes('?') ? '&' : '?') + 'fmt=json3';

    const resp = await fetch(url);
    const data = await resp.json();
    return parseJson3(data);
  }

  async function boot() {
    const videoId = getVideoId();
    if (!videoId) return;

    await new Promise((r) => setTimeout(r, 1500));

    const panel = new LearningPanel({
      platform: 'youtube',
      videoId,
      videoTitle: getVideoTitle(),
      videoUrl: location.href,
      getVideoEl,
      loadCaptions: fetchYouTubeCaptions,
    });
    await panel.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
