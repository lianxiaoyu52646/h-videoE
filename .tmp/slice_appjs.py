from pathlib import Path
p = Path(r'D:\lian\praPro\h-videoE\app\static\m\app.js')
lines = p.read_text(encoding='utf-8').splitlines()
out = Path(r'D:\lian\praPro\h-videoE\.tmp\appjs_slices.txt')
chunks = [(1,80),(500,540),(660,730),(1190,1320),(1358,1420),(1480,1570),(1670,1770)]
parts = []
for a,b in chunks:
    parts.append(f'\n########## {a}-{b} ##########')
    for j in range(a-1, min(len(lines), b)):
        parts.append(f'{j+1:5}|{lines[j]}')
out.write_text('\n'.join(parts), encoding='utf-8')
print('wrote', out, 'chars', out.stat().st_size)
