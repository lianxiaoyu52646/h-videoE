from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
text = p.read_text(encoding="utf-8")

old_paint = '''  function paintDueCardFast() {
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
'''
new_paint = '''  function paintDueCardFast() {
    const due = state.due || [];
    const current = due[0];
    const root = $('#view-vocab');
    const wordEl = $('.flash-word', root);
    if (!current || !wordEl) {
      renderVocab();
      return;
    }
    wordEl.textContent = current.word || '';
    const phon = $('.flash-phonetic', root);
    if (phon) phon.textContent = current.pronunciation || '';
    const meaning = $('.flash-meaning', root);
    if (meaning) meaning.textContent = current.translation || current.definition || '';
    const head = $('.m-card-head h2', root);
    if (head) head.textContent = '\\u4eca\\u65e5\\u7ec3\\u4e60 \\u00b7 \\u5230\\u671f ' + due.length + ' \\u4e2a';
    const speakBtn = $('.flash-card [data-speak-word]', root);
'''
n = text.count(old_paint)
if n != 1:
    raise SystemExit(f"paint scope count={n}")
text = text.replace(old_paint, new_paint, 1)

old_card = '          <div class="flash-card">'
new_card = '          <div class="flash-card is-enter">'
n = text.count(old_card)
if n != 1:
    raise SystemExit(f"flash-card count={n}")
text = text.replace(old_card, new_card, 1)

p.write_text(text, encoding="utf-8")
print("ok scoped paint + is-enter")
