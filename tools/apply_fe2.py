from pathlib import Path
p = Path(r"D:\lian\praPro\h-videoE\app\static\m\app.js")
t = p.read_text(encoding="utf-8")

def once(text, old, new, label):
    if old not in text:
        raise SystemExit("MISSING " + label + "\n" + old[:180])
    return text.replace(old, new, 1)

t = once(t, """          const res = await api(`/api/wordbooks/${s.wordbookId}/study-star`, {
            method: 'POST',
            body: { entry_id: id, starred: on },
          });
          if (res.progress) {
            s.progress = res.progress;
            updateStudyProgressUi();
          }
          toast(on ? '已进生词本' : '已取消');
          refreshVocab().catch(() => {});
""", """          const res = await api(studyStarPath(s), {
            method: 'POST',
            body: s.isVocabBook ? { vocab_id: id, starred: on } : { entry_id: id, starred: on },
          });
          if (res.progress) {
            s.progress = res.progress;
            updateStudyProgressUi();
          }
          toast(s.isVocabBook ? (on ? '仍在生词本' : '已移出') : (on ? '已进生词本' : '已取消'));
          if (!s.isVocabBook) refreshVocab().catch(() => {});
""", "study-star")

t = once(t, "      let url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}`;",
         "      let url = `${studyFeedBase(s)}?limit=${pageSize}`;", "feed url")
t = once(t, "        url = `/api/wordbooks/${s.wordbookId}/study-feed?limit=${limit}&offset=${offset}`;",
         "        url = `${studyFeedBase(s)}?limit=${limit}&offset=${offset}`;", "feed before")
t = once(t, """          data = await api(
            `/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}&offset=${target}`
          );""", """          data = await api(
            `${studyFeedBase(s)}?limit=${pageSize}&offset=${target}`
          );""", "feed resume")
t = once(t, "    api(`/api/wordbooks/${s.wordbookId}/study-feed?limit=${pageSize}&offset=${next}`)",
         "    api(`${studyFeedBase(s)}?limit=${pageSize}&offset=${next}`)", "prefetch")
t = once(t, """      const res = await api(`/api/wordbooks/${s.wordbookId}/study-cursor`, {
        method: 'POST',
        body: { cursor },
      });""", """      const res = await api(studyCursorPath(s), {
        method: 'POST',
        body: { cursor },
      });""", "cursor")

p.write_text(t, encoding="utf-8")
print("api urls ok")
