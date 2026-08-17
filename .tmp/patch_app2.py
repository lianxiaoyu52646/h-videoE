from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
text = p.read_text(encoding="utf-8")

old = '''    $('#openVocabBookBtn')?.addEventListener('click', () => openVocabBook());
    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
    if (current?.word) prefetchSpeak(current.word);
  }

  async function reviewDueCard(know) {
    const card = (state.due || [])[0];
    if (!card || state.reviewBusy) return;
    state.reviewBusy = true;
    $('#reviewKnow')?.setAttribute('disabled', 'disabled');
    $('#reviewUnknown')?.setAttribute('disabled', 'disabled');
    try {
      await api('/api/review', {
        method: 'POST',
        body: { vocab_id: card.id, rating: know ? 4 : 1 },
      });
      state.due = (state.due || []).slice(1);
      renderVocab();
      api('/api/recommendations').then((due) => {
        state.due = due;
        if (state.tab === 'vocab' && !state.study) renderVocab();
      }).catch(() => {});
    } catch (e) { toast(e.message); }
    finally { state.reviewBusy = false; }
  }
'''

new = '''    $('#openVocabBookBtn')?.addEventListener('click', () => openVocabBook());
    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
    if (current?.word) prefetchSpeak(current.word);
    const nxt = due[1];
    if (nxt?.word) prefetchSpeak(nxt.word);
  }

  function paintDueCardFast() {
    const due = state.due || [];
    const current = due[0];
    const wordEl = $('.flash-word');
    if (!current || !wordEl) {
      renderVocab();
      return;
    }
    wordEl.textContent = current.word || '';
    const phon = $('.flash-phonetic');
    if (phon) phon.textContent = current.pronunciation || '';
    const meaning = $('.flash-meaning');
    if (meaning) meaning.textContent = current.translation || current.definition || '';
    const head = $('.m-card-head h2');
    if (head) head.textContent = '\\u4eca\\u65e5\\u7ec3\\u4e60 \\u00b7 \\u5230\\u671f ' + due.length + ' \\u4e2a';
    const speakBtn = $('.flash-card [data-speak-word]');
    if (speakBtn && current.word) {
      speakBtn.setAttribute('data-speak-word', current.word);
      speakBtn.setAttribute('aria-label', '\\u6717\\u8bfb ' + current.word);
    }
    const next = due[1];
    if (next?.word) prefetchSpeak(next.word);
  }

  function reviewDueCard(know) {
    const card = (state.due || [])[0];
    if (!card || state.reviewBusy) return;
    state.reviewBusy = true;
    state.due = (state.due || []).slice(1);
    paintDueCardFast();
    setTimeout(() => { state.reviewBusy = false; }, 180);
    api('/api/review', {
      method: 'POST',
      body: { vocab_id: card.id, rating: know ? 4 : 1 },
    }).catch((e) => {
      state.due = [card, ...(state.due || [])];
      if (state.tab === 'vocab' && !state.study) paintDueCardFast();
      toast(e.message);
    });
    if ((state.due || []).length <= 3) {
      const skip = new Set([card.id, ...((state.due || []).map((c) => c.id))]);
      api('/api/recommendations?limit=24').then((due) => {
        const extra = (due || []).filter((c) => !skip.has(c.id));
        if (!extra.length) return;
        const wasEmpty = !(state.due || []).length;
        state.due = [...(state.due || []), ...extra];
        if (state.tab === 'vocab' && !state.study) {
          if (wasEmpty) renderVocab();
          else paintDueCardFast();
        }
      }).catch(() => {});
    }
  }
'''

n = text.count(old)
if n != 1:
    raise SystemExit(f"reviewDueCard count={n}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
print("ok reviewDueCard")
