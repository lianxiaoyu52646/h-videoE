// ── 练习模块，可独立页使用，也可嵌入生词页 ─────────────────────
(() => {
  const practiceArea = document.getElementById('practiceArea');
  if (!practiceArea) return;

  const practiceFilter = document.getElementById('practiceFilter');
  const sourceFilter = practiceFilter || document.getElementById('videoFilter');
  const tabBtns = Array.from(document.querySelectorAll('#practiceSection .tab-btn, .practice-tabs .tab-btn'));

  let currentType = 'spelling';
  let currentFilter = '';
  let questions = [];
  let qIdx = 0;

  async function practiceApi(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(await resp.text());
    return resp.json();
  }

  function getFilterParam() {
    return currentFilter ? `&source_video_id=${encodeURIComponent(currentFilter)}` : '';
  }

  function escapeHtml(s) {
    return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadPracticeFilter() {
    if (!practiceFilter) {
      currentFilter = sourceFilter?.value || new URLSearchParams(location.search).get('video') || '';
      return;
    }
    try {
      const videos = await practiceApi('/api/vocab/videos');
      const preselect = new URLSearchParams(location.search).get('video') || '';
      practiceFilter.innerHTML = '<option value="">全部生词</option>';
      videos.forEach((v) => {
        const opt = document.createElement('option');
        opt.value = v.source_video_id;
        opt.textContent = `${v.source_title || v.source_video_id} (${v.word_count}词)`;
        practiceFilter.appendChild(opt);
      });
      if (preselect) {
        practiceFilter.value = preselect;
        currentFilter = preselect;
      }
    } catch (_) {}
  }

  sourceFilter?.addEventListener('change', () => {
    currentFilter = sourceFilter.value;
    loadQuestions();
  });

  function speak(text) {
    const w = String(text || '').trim();
    if (!w) return;
    try {
      if (window.AndroidDictionary && typeof window.AndroidDictionary.speak === 'function') {
        window.AndroidDictionary.speak(w);
        return;
      }
    } catch (_) { /* fall through */ }
    if ('speechSynthesis' in window) {
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(w);
      utter.lang = 'en-US';
      utter.rate = 0.8;
      speechSynthesis.speak(utter);
    }
  }

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentType = btn.dataset.type;
      loadQuestions();
    });
  });

  async function loadQuestions() {
    practiceArea.innerHTML = `<p style="color:var(--muted);text-align:center;padding:40px;">加载中...</p>`;
    try {
      questions = await practiceApi(`/api/practice/${currentType}?limit=10${getFilterParam()}`);
      qIdx = 0;
      if (!questions.length) {
        practiceArea.innerHTML = `
          <div class="empty-state">
            <h3>暂无练习数据</h3>
            <p>${currentFilter ? '当前来源下没有足够生词，请换来源或继续收藏。' : '请先在视频、阅读或词书中收藏一些单词。'}</p>
          </div>
        `;
        return;
      }
      renderQuestion();
    } catch (e) {
      practiceArea.innerHTML = `<p style="color:var(--danger)">加载失败: ${escapeHtml(e.message)}</p>`;
    }
  }

  function renderQuestion() {
    if (qIdx >= questions.length) {
      practiceArea.innerHTML = `
        <div class="empty-state">
          <h3>🎉 练习完成！</h3>
          <p>共完成 ${questions.length} 道题。</p>
          <button class="btn-primary" id="restartPracticeBtn">再来一轮</button>
        </div>
      `;
      document.getElementById('restartPracticeBtn')?.addEventListener('click', loadQuestions);
      return;
    }

    const q = questions[qIdx];

    if (currentType === 'spelling') renderSpelling(q);
    else if (currentType === 'listening') renderListening(q);
    else if (currentType === 'reading') renderReading(q);
    else if (currentType === 'context') renderContext(q);
  }

  function renderSpelling(q) {
    practiceArea.innerHTML = `
      <div class="practice-question">
        <div class="pq-text">${escapeHtml(q.question)}</div>
        ${q.pronunciation ? `<div style="color:var(--accent);margin-bottom:16px;">${escapeHtml(q.pronunciation)}</div>` : ''}
        <input type="text" id="answerInput" placeholder="输入英文单词..." autocomplete="off" />
        <div><button class="btn-primary" id="submitBtn">提交</button></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const input = document.getElementById('answerInput');
    input.focus();
    document.getElementById('submitBtn').addEventListener('click', () => checkSpelling(q, input.value));
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') checkSpelling(q, input.value);
    });
  }

  function checkSpelling(q, answer) {
    const msg = document.getElementById('resultMsg');
    if (answer.trim().toLowerCase() === q.answer.toLowerCase()) {
      msg.textContent = '✅ 正确！';
      msg.className = 'result-msg correct';
    } else {
      msg.textContent = `❌ 错误！正确答案: ${q.answer}`;
      msg.className = 'result-msg wrong';
    }
    setTimeout(() => { qIdx += 1; renderQuestion(); }, 2000);
  }

  function renderListening(q) {
    practiceArea.innerHTML = `
      <div class="practice-question">
        <button class="tts-btn" id="playBtn">🔊 点击播放</button>
        <div class="pq-text">听录音并拼写单词</div>
        <input type="text" id="answerInput" placeholder="输入听到的单词..." autocomplete="off" />
        <div><button class="btn-primary" id="submitBtn">提交</button></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const input = document.getElementById('answerInput');
    document.getElementById('playBtn').addEventListener('click', () => speak(q.answer));
    document.getElementById('submitBtn').addEventListener('click', () => {
      const msg = document.getElementById('resultMsg');
      if (input.value.trim().toLowerCase() === q.answer.toLowerCase()) {
        msg.textContent = '✅ 正确！';
        msg.className = 'result-msg correct';
      } else {
        msg.textContent = `❌ 错误！正确答案: ${q.answer}`;
        msg.className = 'result-msg wrong';
      }
      setTimeout(() => { qIdx += 1; renderQuestion(); }, 2000);
    });
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') document.getElementById('submitBtn').click();
    });
  }

  function renderContext(q) {
    practiceArea.innerHTML = `
      <div class="practice-question">
        <p class="pq-hint">根据原句语境，填入正确的单词</p>
        <div class="pq-text pq-context">${escapeHtml(q.question)}</div>
        ${q.definition ? `<div class="pq-def-hint">提示：${escapeHtml(q.definition)}</div>` : ''}
        <input type="text" id="answerInput" class="practice-input" placeholder="输入单词..." autocomplete="off" />
        <button id="submitBtn" class="btn-primary">提交</button>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const input = document.getElementById('answerInput');
    input.focus();
    document.getElementById('submitBtn').addEventListener('click', () => {
      const val = input.value.trim();
      const msg = document.getElementById('resultMsg');
      const correct = val.toLowerCase() === q.answer.toLowerCase();
      input.disabled = true;
      document.getElementById('submitBtn').disabled = true;
      if (correct) {
        msg.textContent = '✅ 正确！';
        msg.className = 'result-msg correct';
      } else {
        msg.textContent = `❌ 错误！正确答案: ${q.answer}`;
        msg.className = 'result-msg wrong';
      }
      setTimeout(() => { qIdx += 1; renderQuestion(); }, 2000);
    });
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') document.getElementById('submitBtn').click();
    });
  }

  function renderReading(q) {
    practiceArea.innerHTML = `
      <div class="practice-question">
        <div class="pq-text">${escapeHtml(q.question)}</div>
        <div class="choice-list" id="choiceList"></div>
        <div id="resultMsg" class="result-msg"></div>
      </div>
    `;
    const list = document.getElementById('choiceList');
    q.choices.forEach((choice) => {
      const btn = document.createElement('button');
      btn.className = 'choice-item';
      btn.textContent = choice;
      btn.addEventListener('click', () => {
        const msg = document.getElementById('resultMsg');
        const buttons = list.querySelectorAll('.choice-item');
        buttons.forEach((b) => { b.disabled = true; });
        if (choice === q.answer) {
          btn.classList.add('correct');
          msg.textContent = '✅ 正确！';
          msg.className = 'result-msg correct';
        } else {
          btn.classList.add('wrong');
          buttons.forEach((b) => {
            if (b.textContent === q.answer) b.classList.add('correct');
          });
          msg.textContent = `❌ 错误！正确答案: ${q.answer}`;
          msg.className = 'result-msg wrong';
        }
        setTimeout(() => { qIdx += 1; renderQuestion(); }, 2000);
      });
      list.appendChild(btn);
    });
  }

  window.addEventListener('load', async () => {
    currentFilter = new URLSearchParams(location.search).get('video') || sourceFilter?.value || '';
    await loadPracticeFilter();
    await loadQuestions();
  });
})();
