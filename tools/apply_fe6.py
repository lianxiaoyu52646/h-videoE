from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")
old = """  /** FSRS review only: 会→Good(4), 不会→Again(1). Never delete the card here. */
  async function reviewDueCard(know) {
    const card = (state.due || [])[0];
    if (!card) return;
    try {
      // Frontend shows only 会/不会; finer FSRS state stays in DB.
      await api('/api/review', {
        method: 'POST',
        body: { vocab_id: card.id, rating: know ? 4 : 1 },
      });
      toast(know ? '会，已按计划延后' : '不会，稍后还会推送');
      await loadVocab();
      renderVocab();
    } catch (e) { toast(e.message); }
  }
"""
if old not in t:
    # print nearby
    i = t.find("/** FSRS review only")
    print("NOT FOUND, nearby:")
    print(t[i:i+700])
    raise SystemExit("old reviewDueCard missing")
t = t.replace(old, "  /** FSRS review only: 会→Good(4), 不会→Again(1). Never delete the card here. */\n", 1)
p.write_text(t, encoding="utf-8")
print("removed duplicate", p.read_text(encoding="utf-8").count("async function reviewDueCard"))
