from pathlib import Path
p = Path(r'D:\lian\praPro\h-videoE\app\crud.py')
lines = p.read_text(encoding='utf-8').splitlines()
out = []
for i,l in enumerate(lines):
    if 'def get_vocab_card' in l or 'def _apply_user_scope' in l:
        out.append(f'\n===== {i+1} {l} =====')
        for j in range(i, min(len(lines), i+40)):
            out.append(f'{j+1:5}|{lines[j]}')
Path(r'D:\lian\praPro\h-videoE\.tmp\crud_snip.txt').write_text('\n'.join(out), encoding='utf-8')
print('ok', len(out))
