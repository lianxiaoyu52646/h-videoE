from pathlib import Path

p = Path(r"D:\lian\praPro\h-videoE\app\static\css\mobile.css")
text = p.read_text(encoding="utf-8")

old_list = '''.study-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.study-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 16px 14px;
  margin-bottom: 0;
  background: #fff;
  border-radius: 22px;
  border: 1px solid var(--stroke);
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  position: relative;
}'''
new_list = '''.study-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  contain: content;
}
.study-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 16px 14px;
  margin-bottom: 0;
  background: #fff;
  border-radius: 22px;
  border: 1px solid var(--stroke);
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  position: relative;
  contain: layout style;
}'''
n = text.count(old_list)
if n != 1:
    raise SystemExit(f"study-list count={n}")
text = text.replace(old_list, new_list, 1)

old_flash = '''  padding: 28px 16px;
  margin-bottom: 14px;
  animation: heroIn 0.35s ease both;
  overflow-anchor: none;
}'''
new_flash = '''  padding: 28px 16px;
  margin-bottom: 14px;
  overflow-anchor: none;
}
.flash-card.is-enter {
  animation: heroIn 0.35s ease both;
}'''
n = text.count(old_flash)
if n != 1:
    raise SystemExit(f"flash anim count={n}")
text = text.replace(old_flash, new_flash, 1)

old_bin = '''.binary-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}'''
new_bin = '''.binary-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  touch-action: manipulation;
}
.binary-actions .m-btn { touch-action: manipulation; }'''
n = text.count(old_bin)
if n != 1:
    raise SystemExit(f"binary count={n}")
text = text.replace(old_bin, new_bin, 1)

p.write_text(text, encoding="utf-8")
print("ok mobile.css")
