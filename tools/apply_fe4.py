from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")

def once(text, old, new, label):
    if old not in text:
        raise SystemExit("MISSING " + label)
    return text.replace(old, new, 1)

old = """  function renderVocab() {
    const root = $('#view-vocab');
    const due = state.due || [];
    const current = due[0];
    const warehouse = state.vocab || [];
"""
if old not in t:
    raise SystemExit("renderVocab head missing")

# Replace from function start through reviewDueCard end by locating markers
start = t.find("  function renderVocab() {")
end = t.find("  /** FSRS review only:")
if start < 0 or end < 0:
    raise SystemExit(f"markers {start} {end}")

new = r"""  function renderVocab() {
    const root = $('#view-vocab');
    const due = state.due || [];
    const current = due[0];
    root.innerHTML = `
      <div class="m-hero">
        <h1>生词 · 记忆</h1>
        <p>到期词逐个练习。完整列表在「生词书」里，和词书一样记住位置。</p>
      </div>
      <div class="m-card">
        <div class="m-card-head">
          <h2>今日练习 · 到期 ${due.length} 个</h2>
          <button class="m-btn m-btn-primary" id="openVocabBookBtn" type="button">生词书</button>
        </div>
        <p class="m-muted" style="margin:0 0 12px;">「会」延后复习，「不会」尽快再练。练习不会删词。</p>
        ${current ? `
          <div class="flash-card">
            <div class="flash-word-row">
              <div class="flash-word">${escapeHtml(current.word)}</div>
              ${speakBtnHtml(current.word, 'speak-btn-lg')}
            </div>
            <div class="flash-phonetic">${escapeHtml(current.pronunciation || '')}</div>
            <div class="flash-meaning">${escapeHtml(current.translation || current.definition || '')}</div>
          </div>
          <div class="binary-actions">
            <button class="m-btn m-btn-mint" id="reviewKnow" type="button">会</button>
            <button class="m-btn m-btn-danger" id="reviewUnknown" type="button">不会</button>
          </div>
        ` : '<p class="m-muted">暂无到期词。去阅读 / 词书 / 对战收藏生词后，到期会自动出现在这里。</p>'}
      </div>`;

    $('#openVocabBookBtn')?.addEventListener('click', () => openVocabBook());
    $('#reviewKnow')?.addEventListener('click', () => reviewDueCard(true));
    $('#reviewUnknown')?.addEventListener('click', () => reviewDueCard(false));
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

"""
t = t[:start] + new + t[end:]
p.write_text(t, encoding="utf-8")
print("renderVocab/reviewDueCard ok", start, end)
